"""core/mascot_controller.py – Orchestrateur avec détection auto des personnages."""
from __future__ import annotations
import asyncio
import json
import random
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QTimer, Qt
from core.conversation_manager import ConversationManager
from core.system_reactor import SystemReactor
from core.minigame_manager import MinigameManager
from PyQt6.QtWidgets import QApplication, QFileDialog

from config import Config
from core.sprite_engine import SpriteEngine
from core.behavior import BehaviorEngine
from core.physics import PhysicsEngine
from core.window_detector import WindowDetector
from core.monitor_manager import MonitorManager
from ai.client import AIClient
from ai.memory import MemoryManager
from ui.mascot_window import MascotWindow
from ui.chat_window import ChatWindow


class MascotController:
    def __init__(self, config: Config):
        self.config   = config
        self.mascots: list[MascotWindow] = []
        self.chat_windows: dict[int, ChatWindow] = {}
        self._mascot_counter = 0

        self.monitors        = MonitorManager()
        self.window_detector = WindowDetector()
        self.memory          = MemoryManager(max_messages=config.memory_max_messages)
        self.ai_client       = AIClient(config, self.memory)
        self.conversation_mgr = ConversationManager(self)
        self.system_reactor  = SystemReactor(self)
        self.minigame_mgr    = MinigameManager(self)

        # Détection des personnages disponibles
        self._available_chars: list[Path] = self._discover_characters()
        if self._available_chars:
            print(f"[Controller] {len(self._available_chars)} personnages disponibles :")
            for c in self._available_chars:
                print(f"  • {c.name}")

        self._win_timer = QTimer()
        self._win_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._win_timer.timeout.connect(self._refresh_windows)
        self._win_timer.start(config.window_refresh_ms)

        self._mon_timer = QTimer()
        self._mon_timer.timeout.connect(self.monitors.refresh)
        self._mon_timer.start(5000)

        # Timer mutualisé : PreciseTimer pour minimiser le jitter à 30fps
        self._mascot_timer = QTimer()
        self._mascot_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._mascot_timer.timeout.connect(self._tick_all)
        self._mascot_timer.start(max(16, 1000 // max(1, config.fps)))

        # Restaurer la session précédente
        self._load_session()

    # ── Découverte automatique des personnages ─────────────────────────

    def _discover_characters(self) -> list[Path]:
        """
        Cherche tous les sous-dossiers valides dans assets/img/ ou assets/
        qui contiennent des PNG ou un conf/actions.xml.
        """
        chars: list[Path] = []
        base = Path(self.config.character_path)

        # Dossier configuré directement
        if self._is_valid_char_dir(base):
            chars.append(base)

        # Cherche dans assets/default/img/ ou assets/img/
        search_roots = [
            base.parent,            # assets/default/img/ → assets/default/
            base.parent.parent,     # assets/default/ → assets/
            Path("assets") / "img",
            Path("assets") / "default" / "img",
        ]

        seen_names: set[str] = {p.name for p in chars}
        for root in search_roots:
            if root.exists() and root.is_dir():
                for sub in sorted(root.iterdir()):
                    if sub.is_dir() and self._is_valid_char_dir(sub):
                        if sub.name not in seen_names:
                            seen_names.add(sub.name)
                            chars.append(sub)

        return chars

    def _is_valid_char_dir(self, path: Path) -> bool:
        """Un dossier de personnage valide doit avoir conf/actions.xml ET au moins un PNG."""
        if not path.exists() or not path.is_dir():
            return False
        # Doit avoir un fichier XML d'actions
        if not (path / "conf" / "actions.xml").exists():
            return False
        # Doit avoir au moins un PNG (sprites)
        pngs = list(path.glob("*.png")) + list(path.glob("*.PNG"))
        if pngs:
            return True
        img_sub = path / "img"
        if img_sub.exists():
            return bool(list(img_sub.glob("*.png")) + list(img_sub.glob("*.PNG")))
        return False

    def available_characters(self) -> list[Path]:
        return list(self._available_chars)

    # ── Spawn ─────────────────────────────────────────────────────────

    def spawn_mascot(self, character_path: Optional[str] = None) -> Optional[MascotWindow]:
        if len(self.mascots) >= self.config.max_mascots:
            return None  # silencieux — pas de print spam

        path_str = character_path or self.config.character_path
        path     = Path(path_str)

        if not path.exists():
            print(f"[Controller] Chemin introuvable : {path}")
            if self._available_chars:
                path = self._available_chars[0]
                print(f"[Controller] Fallback sur : {path}")
            else:
                return None

        try:
            sprite   = SpriteEngine(str(path), scale=self.config.mascot_scale)
            behavior = BehaviorEngine(str(path), config=self.config)
            physics  = PhysicsEngine(
                self.monitors,
                self.window_detector,
                walk_speed=self.config.walk_speed,
                gravity=self.config.gravity,
            )
        except Exception as e:
            print(f"[Controller] Erreur chargement : {e}")
            import traceback; traceback.print_exc()
            return None

        # Informer le behavior engine des actions disponibles
        behavior.set_available_actions(set(sprite.action_names()))

        self._randomize_spawn(physics)

        # Lier ce perso aux autres pour les interactions physiques
        physics.other_mascots = [m.physics for m in self.mascots]
        for m in self.mascots:
            m.physics.other_mascots.append(physics)

        mascot_id = self._mascot_counter
        self._mascot_counter += 1

        char_name = path.name
        window = MascotWindow(sprite, behavior, physics, self.config, mascot_id,
                              character_name=char_name)
        window._controller    = self   # référence pour ProfileDialog
        window._mood_indicator = None  # initialisé après show()
        window.chat_requested.connect(self._open_chat)
        window.clone_requested.connect(self._clone_mascot)
        window.dismiss_requested.connect(self.dismiss_mascot)

        self.mascots.append(window)
        print(f"[Controller] Personnage #{mascot_id} spawné ({path.name})")
        # Créer l'indicateur d'humeur
        if getattr(self.config, "enable_mood_indicator", True):
            try:
                from ui.mood_indicator import MoodIndicator
                window._mood_indicator = MoodIndicator(window)
                window._mood_indicator.set_mood('neutral')
            except Exception as e:
                print(f'[Controller] Humeur impossible : {e}')

        # Auto-générer la personnalité si pas encore définie
        if char_name not in self.config.character_personalities:
            asyncio.ensure_future(self._auto_personality(char_name))

        self._save_session()
        return window

    def spawn_random(self) -> Optional[MascotWindow]:
        """Spawne un personnage aléatoire parmi ceux disponibles."""
        if not self._available_chars:
            return self.spawn_mascot()
        return self.spawn_mascot(str(random.choice(self._available_chars)))

    def spawn_from_dialog(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            None, "Choisir un dossier de personnage Shimeji", "assets/",
        )
        if folder:
            self.spawn_mascot(folder)

    def dismiss_mascot(self, mascot: MascotWindow) -> None:
        self.conversation_mgr.cancel_if_involved(mascot)
        # Fermer l'indicateur d'humeur
        try:
            if hasattr(mascot, '_mood_indicator') and mascot._mood_indicator:
                mascot._mood_indicator.fade_out_and_close()
        except Exception:
            pass
        self.system_reactor._sleep_states.pop(mascot.mascot_id, None)
        if mascot in self.mascots:
            self.mascots.remove(mascot)
        # Retirer de la liste des interactions des autres
        for m in self.mascots:
            try:
                m.physics.other_mascots = [
                    p for p in m.physics.other_mascots if p is not mascot.physics
                ]
            except Exception:
                pass
        mid = mascot.mascot_id
        if mid in self.chat_windows:
            self.chat_windows[mid].close()
            del self.chat_windows[mid]
        # Arrêter tout ThrowIE actif de ce perso
        try:
            mascot.physics.state.throw_active = False
            mascot.physics.state.held_hwnd = 0
        except Exception:
            pass
        mascot.close_mascot()
        self._save_session()

    def dismiss_all(self) -> None:
        for m in list(self.mascots):
            self.dismiss_mascot(m)
        self._save_session()

    # ── Chat ──────────────────────────────────────────────────────────

    def _open_chat(self, mascot: MascotWindow) -> None:
        mid = mascot.mascot_id
        if mid not in self.chat_windows:
            # Créer une config spécifique à ce perso (nom correct)
            from dataclasses import replace as dc_replace
            char_config = dc_replace(self.config, character_name=mascot.character_name)
            self.chat_windows[mid] = ChatWindow(mascot, self.ai_client, char_config)
        self.chat_windows[mid].toggle()
        mascot.behavior.notify_talking(self.chat_windows[mid].isVisible())

    def _clone_mascot(self, mascot: MascotWindow) -> None:
        # Clone avec un perso aléatoire différent si possible
        current_name = Path(mascot.sprite.path).name if hasattr(mascot.sprite, 'path') else ''
        other = [c for c in self._available_chars if c.name != current_name]
        target = str(random.choice(other)) if other else self.config.character_path
        self.spawn_mascot(target)

    # ── Spawn position ────────────────────────────────────────────────

    def _randomize_spawn(self, physics: PhysicsEngine) -> None:
        screen = QApplication.primaryScreen()
        if screen:
            geo    = screen.geometry()
            # Marge de 25% de chaque côté pour éviter les bords
            margin = geo.width() // 4
            x = random.randint(geo.left() + margin, geo.right() - margin)
            y = geo.bottom()
            print(f"[Controller] Spawn à ({x}, {y}) écran {geo.width()}x{geo.height()}")
        else:
            x, y = 960, 1080
        physics.teleport(float(x), float(y))

    # ── Utilitaires ───────────────────────────────────────────────────

    def _save_session(self) -> None:
        """Sauvegarde les personnages actifs pour la prochaine session."""
        session = {
            "mascots": [str(m.sprite.path) for m in self.mascots]
        }
        try:
            Path("session.json").write_text(json.dumps(session, indent=2))
        except Exception as e:
            print(f"[Session] Erreur sauvegarde: {e}")

    def _load_session(self) -> None:
        """Restaure les personnages de la session précédente."""
        session_file = Path("session.json")
        if not session_file.exists():
            return
        try:
            data = json.loads(session_file.read_text())
            paths = data.get("mascots", [])
            if paths:
                print(f"[Session] Restauration de {len(paths)} personnage(s)")
                for p in paths:
                    if Path(p).exists():
                        self.spawn_mascot(p)
        except Exception as e:
            print(f"[Session] Erreur chargement: {e}")

    def _refresh_windows(self) -> None:
        self.window_detector.refresh()

    def _tick_all(self) -> None:
        """Tick mutualisé : appelé 30x/s pour tous les persos en même temps."""
        # Conversations entre mascots
        if getattr(self.config, "enable_conversations", True):
            self.conversation_mgr.tick(self.mascots)
        # Réactions heure/système
        if getattr(self.config, "enable_system_reactions", True):
            self.system_reactor.tick(self.mascots)
        # Mini-jeux
        if getattr(self.config, "enable_minigames", True):
            self.minigame_mgr.tick(self.mascots)

        # Pré-calculer les positions de tous les persos pour les interactions
        positions = [(m, m.physics.state.feet_x, m.physics.state.feet_y)
                     for m in self.mascots]

        for m in self.mascots:
            try:
                # Trouver le voisin le plus proche sur le même sol
                fx, fy = m.physics.state.feet_x, m.physics.state.feet_y
                nearest_x: Optional[float] = None
                nearest_dist = float('inf')
                for other, ox, oy in positions:
                    if other is m:
                        continue
                    if abs(oy - fy) > 50:  # pas sur le même niveau
                        continue
                    d = abs(ox - fx)
                    if d < nearest_dist:
                        nearest_dist = d
                        nearest_x = ox
                m.behavior.set_neighbor_x(nearest_x)
                m.tick()
            except Exception as e:
                print(f"[Controller] Erreur tick mascot #{m.mascot_id}: {e}")

    async def _auto_personality(self, char_name: str) -> None:
        """Génère automatiquement la personnalité d'un perso via l'IA au premier spawn.
        Ne s'exécute que si aucune personnalité n'est déjà définie.
        L'utilisateur peut toujours la modifier manuellement ensuite."""
        try:
            print(f"[Controller] Génération de personnalité pour {char_name}...")
            prompt = (
                f"Décris la personnalité de {char_name} en 3-4 phrases courtes, "
                f"comme si tu décrivais un assistant de bureau avec ce personnage. "
                f"Concentre-toi sur son caractère, ses traits distinctifs, son ton. "
                f"Si c'est un personnage de jeu vidéo, d'anime ou de fiction, "
                f"base-toi sur sa personnalité canonique. "
                f"Réponds UNIQUEMENT avec la description, sans introduction ni conclusion. "
                f"En français."
            )
            system = (
                "Tu es un expert en personnages de jeux vidéo, d'anime et de culture pop. "
                "Tu connais les personnages d'Arknights, de mangas, de jeux RPG, etc. "
                "Tu décris leur personnalité de façon concise et fidèle."
            )
            # Utiliser un character_name spécial pour ne pas polluer l'historique
            old = self.config.character_personalities.get("__autopersonality__", "")
            self.config.character_personalities["__autopersonality__"] = system
            result = ""
            try:
                result = await self.ai_client.chat(prompt, "__autopersonality__")
            finally:
                if old:
                    self.config.character_personalities["__autopersonality__"] = old
                else:
                    self.config.character_personalities.pop("__autopersonality__", None)
                self.memory.clear("__autopersonality__")

            if result and not result.startswith("[Erreur"):
                self.config.set_personality(char_name, result)
                self.config.save()
                print(f"[Controller] Personnalité générée pour {char_name} : {result[:60]}...")
            else:
                print(f"[Controller] Impossible de générer la personnalité pour {char_name}")
        except Exception as e:
            print(f"[Controller] Erreur génération personnalité : {e}")

    def reload_ai(self) -> None:
        import asyncio
        import threading
        old_client = self.ai_client
        self.ai_client = AIClient(self.config, self.memory)
        for chat in self.chat_windows.values():
            chat.ai_client = self.ai_client
        def _close_old():
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(old_client.close())
            except Exception:
                pass
            finally:
                loop.close()
        threading.Thread(target=_close_old, daemon=True).start()
