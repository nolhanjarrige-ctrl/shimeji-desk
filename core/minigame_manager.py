"""core/minigame_manager.py — Mini-jeux entre mascots (pierre-feuille-ciseaux)."""
from __future__ import annotations
import asyncio
import random
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.mascot_controller import MascotController

CHOICES    = ["✊ Pierre", "✋ Feuille", "✌ Ciseaux"]
WINS_OVER  = {"✊ Pierre": "✌ Ciseaux", "✋ Feuille": "✊ Pierre", "✌ Ciseaux": "✋ Feuille"}
COOLDOWN   = 30 * 60 * 5   # 5 minutes
PROXIMITY  = 150            # px


class MinigameManager:

    def __init__(self, controller: "MascotController"):
        self._ctrl     = controller
        self._cooldown = 0
        self._active   = False

    def tick(self, mascots: list) -> None:
        if self._cooldown > 0:
            self._cooldown -= 1
            return
        if self._active or len(mascots) < 2:
            return
        # 0.3% de chance par tick de déclencher un mini-jeu (~30fps → ~toutes les 10min)
        if random.random() > 0.003:
            return
        # Trouver deux persos proches au sol
        for i, a in enumerate(mascots):
            for b in mascots[i+1:]:
                dist = abs(a.physics.state.feet_x - b.physics.state.feet_x)
                same = abs(a.physics.state.feet_y - b.physics.state.feet_y) < 60
                a_floor = a.physics.state.on_any_floor
                b_floor = b.physics.state.on_any_floor
                if dist < PROXIMITY and same and a_floor and b_floor:
                    self._active = True
                    asyncio.ensure_future(self._run_pfc(a, b))
                    return

    async def _run_pfc(self, a, b) -> None:
        from core.behavior import State
        from ui.mascot_bubble import MascotBubble

        name_a = a.character_name
        name_b = b.character_name

        try:
            if not getattr(self._ctrl.config, "enable_bubbles", True):
                return
            # Se faire face
            fx_a = a.physics.state.feet_x
            fx_b = b.physics.state.feet_x
            a.behavior.look_right = fx_a > fx_b
            b.behavior.look_right = fx_b > fx_a
            a.behavior.notify_talking(True)
            b.behavior.notify_talking(True)
            await asyncio.sleep(0.3)

            # Annonce
            bubble_a = MascotBubble(a, name_a)
            bubble_a.set_text("Pierre, feuille, ciseaux !")
            await asyncio.sleep(2.0)
            bubble_a.fade_out(then_close=True)
            await asyncio.sleep(0.3)

            bubble_b = MascotBubble(b, name_b)
            bubble_b.set_text("C'est parti !")
            await asyncio.sleep(1.5)
            bubble_b.fade_out(then_close=True)
            await asyncio.sleep(0.3)

            # Choix
            choice_a = random.choice(CHOICES)
            choice_b = random.choice(CHOICES)

            # Révéler simultanément
            bub_a2 = MascotBubble(a, name_a)
            bub_a2.set_text(choice_a)
            bub_b2 = MascotBubble(b, name_b)
            bub_b2.set_text(choice_b)
            await asyncio.sleep(2.5)

            # Résultat
            if choice_a == choice_b:
                result_a, result_b = "Égalité !", "Égalité !"
                score_delta = 0
            elif WINS_OVER[choice_a] == choice_b:
                result_a = "J'ai gagné ! 🎉"
                result_b = "J'ai perdu... 😔"
                score_delta = +1
                winner, loser = name_a, name_b
            else:
                result_a = "J'ai perdu... 😔"
                result_b = "J'ai gagné ! 🎉"
                score_delta = +1
                winner, loser = name_b, name_a

            bub_a2.fade_out(then_close=True)
            bub_b2.fade_out(then_close=True)
            await asyncio.sleep(0.4)

            bub_a3 = MascotBubble(a, name_a)
            bub_a3.set_text(result_a)
            bub_b3 = MascotBubble(b, name_b)
            bub_b3.set_text(result_b)
            await asyncio.sleep(2.5)

            bub_a3.fade_out(then_close=True)
            bub_b3.fade_out(then_close=True)

            # Mettre à jour la relation (gagnant-perdant)
            if score_delta != 0:
                self._ctrl.memory.update_relation(
                    name_a, name_b, score_delta,
                    f"jeu PFC remporté par {winner if score_delta > 0 and choice_a != choice_b else name_b}"
                )
            # Mettre à jour l'humeur
            self._update_moods(a, b, choice_a, choice_b)

        except Exception as e:
            print(f"[MinigameManager] Erreur : {e}")
        finally:
            try: a.behavior.notify_talking(False)
            except Exception: pass
            try: b.behavior.notify_talking(False)
            except Exception: pass
            self._active   = False
            self._cooldown = COOLDOWN

    def _update_moods(self, a, b, choice_a: str, choice_b: str) -> None:
        """Met à jour l'humeur des persos selon le résultat."""
        try:
            if choice_a == choice_b:
                mood_a = mood_b = "neutral"
            elif WINS_OVER[choice_a] == choice_b:
                mood_a = "excited"
                mood_b = "sad"
            else:
                mood_a = "sad"
                mood_b = "excited"

            if hasattr(a, '_mood_indicator') and a._mood_indicator:
                a._mood_indicator.set_mood(mood_a)
            if hasattr(b, '_mood_indicator') and b._mood_indicator:
                b._mood_indicator.set_mood(mood_b)
        except Exception:
            pass
