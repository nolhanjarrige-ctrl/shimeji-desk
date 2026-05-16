"""core/conversation_manager.py — Conversations entre mascots."""
from __future__ import annotations
import asyncio
import random
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.mascot_controller import MascotController

# ── Constantes ──────────────────────────────────────────────────────────────
PROXIMITY_PX    = 180
PROXIMITY_TICKS = 90
COOLDOWN_TICKS  = 600
BUBBLE_LINGER_MS = 3000

# ── Scénarios (poids, label, min, max, description, longueur_réponse) ──────
# longueur_réponse : "courte" | "normale" | "longue"
SCENARIOS = [
    (30, "salutation",    1, 2,
     "Une salutation spontanée, chaleureuse mais très brève. "
     "Comme croiser quelqu'un dans un couloir.", "courte"),

    (20, "au_revoir",     1, 2,
     "Se dire au revoir avec une touche d'émotion ou d'humour. "
     "Bref mais mémorable.", "courte"),

    (15, "chemin",        2, 3,
     "L'un demande quelque chose à l'autre (direction, conseil, info). "
     "Contexte : ils sont des personnages sur un bureau d'ordinateur, "
     "tout peut être absurde et drôle.", "normale"),

    (25, "discussion",    3, 6,
     "Conversation naturelle : ils partagent un avis, racontent quelque chose, "
     "commentent leur journée ou ce qui se passe autour d'eux. "
     "Chaque réplique rebondit vraiment sur la précédente.", "normale"),

    (20, "commérage",     3, 5,
     "Ils commentent discrètement quelque chose ou quelqu'un — "
     "ce que fait l'utilisateur, un autre perso, quelque chose sur l'écran. "
     "Ton espiègle, curieux, légèrement complice.", "normale"),

    (15, "question",      3, 6,
     "L'UN pose une vraie question à l'autre. L'autre doit répondre "
     "COMPLÈTEMENT et en détail avant que la conversation puisse évoluer. "
     "Ne pas esquiver la question, ne pas répondre par une autre question. "
     "Réponse longue et développée autorisée.", "longue"),

    (10, "philosophique", 5, 8,
     "Discussion profonde et absurde sur leur existence comme mascots de bureau : "
     "le sens de leur vie, ce qu'ils pensent de l'utilisateur, "
     "leurs peurs et leurs rêves. Prendre le temps de développer les idées. "
     "Pas de conclusions trop rapides.", "longue"),

    ( 8, "dispute",       4, 7,
     "Désaccord vrai mais amusant sur quelque chose d'anodin. "
     "Chacun défend vraiment son point de vue avec des arguments. "
     "Pas de capitulation immédiate. Se termine par une réconciliation "
     "ou un statu quo frustrant.", "normale"),

    ( 7, "blague",        2, 5,
     "L'un essaie de raconter une blague, une anecdote drôle ou de faire "
     "de l'humour. L'autre réagit sincèrement — ça peut tomber à plat "
     "ou provoquer un vrai échange comique.", "normale"),
]

# ── Activités sociales ────────────────────────────────────────────────────────
# (poids, label, description) — ce que font les persos PENDANT la conversation
SOCIAL_ACTIVITIES = [
    (40, "assis",      "Les deux personnages sont assis côte à côte et discutent."),
    (30, "debout",     "Les deux sont debout, face à face, en train de parler."),
    (20, "marche",     "Les deux marchent côte à côte dans la même direction "
                       "tout en discutant."),
    (10, "un_assis",   "L'un est assis, l'autre est debout à côté."),
]


def _pick_scenario():
    total = sum(s[0] for s in SCENARIOS)
    r, cum = random.uniform(0, total), 0
    for s in SCENARIOS:
        cum += s[0]
        if r <= cum:
            return s
    return SCENARIOS[0]


def _pick_activity():
    total = sum(a[0] for a in SOCIAL_ACTIVITIES)
    r, cum = random.uniform(0, total), 0
    for a in SOCIAL_ACTIVITIES:
        cum += a[0]
        if r <= cum:
            return a
    return SOCIAL_ACTIVITIES[0]


class ConversationManager:

    def __init__(self, controller: "MascotController"):
        self._ctrl       = controller
        self._active     = False
        self._cooldown   = 0
        self._prox_ticks: dict[tuple, int] = {}
        self._pair: Optional[tuple] = None
        self._walking_back: bool = False

    def cancel_if_involved(self, mascot) -> None:
        if self._pair and mascot in self._pair:
            self._active   = False
            self._pair     = None
            self._cooldown = COOLDOWN_TICKS // 2
            mid = mascot.mascot_id
            self._prox_ticks = {k: v for k, v in self._prox_ticks.items()
                                if mid not in k}

    def tick(self, mascots: list) -> None:
        if self._cooldown > 0:
            self._cooldown -= 1

        # Enforcer la direction face-à-face en continu pendant la conversation
        if self._active and self._pair:
            a, b = self._pair
            if a in mascots and b in mascots:
                self._enforce_facing(a, b)
                self._enforce_proximity(a, b)
            return

        if len(mascots) < 2:
            return
        for i, a in enumerate(mascots):
            for b in mascots[i+1:]:
                dist       = abs(a.physics.state.feet_x - b.physics.state.feet_x)
                same_level = abs(a.physics.state.feet_y - b.physics.state.feet_y) < 60
                key        = (a.mascot_id, b.mascot_id)
                if dist < PROXIMITY_PX and same_level:
                    # Ne déclencher que si les deux sont au sol (pas sur mur/plafond)
                    a_grounded = a.physics.state.on_any_floor
                    b_grounded = b.physics.state.on_any_floor
                    if not a_grounded or not b_grounded:
                        self._prox_ticks[key] = 0
                        continue
                    self._prox_ticks[key] = self._prox_ticks.get(key, 0) + 1
                    if self._prox_ticks[key] >= PROXIMITY_TICKS:
                        self._prox_ticks[key] = 0
                        self._start_conversation(a, b)
                        return
                else:
                    self._prox_ticks[key] = 0

    def _start_conversation(self, a, b) -> None:
        self._active = True
        self._pair   = (a, b)
        scenario     = _pick_scenario()
        activity     = _pick_activity()
        n_exchanges  = random.randint(scenario[2], scenario[3])
        print(f"[Conv] {a.character_name} ↔ {b.character_name} "
              f"— {scenario[1]} ({n_exchanges} échanges) · activité: {activity[1]}")
        try:
            asyncio.ensure_future(
                self._run_conversation(a, b, scenario, activity, n_exchanges)
            )
        except RuntimeError:
            self._active = False

    def _enforce_facing(self, a, b) -> None:
        """Force les deux persos à se faire face — appelé à 30fps."""
        try:
            fx_a = a.physics.state.feet_x
            fx_b = b.physics.state.feet_x
            if abs(fx_a - fx_b) > 10:
                a.behavior.look_right = fx_a > fx_b
                b.behavior.look_right = fx_b > fx_a
        except Exception:
            pass

    def _enforce_proximity(self, a, b) -> None:
        """Rapproche les persos s'ils dérivent trop loin pendant la conversation."""
        try:
            from core.behavior import State
            fx_a = a.physics.state.feet_x
            fx_b = b.physics.state.feet_x
            dist = abs(fx_a - fx_b)

            if dist > PROXIMITY_PX * 2 and not self._walking_back:
                self._walking_back = True
                if a.behavior._state in (State.TALKING, State.STAND, State.SIT):
                    a.behavior.force_state(State.WALK_RIGHT if fx_b > fx_a else State.WALK_LEFT)
                if b.behavior._state in (State.TALKING, State.STAND, State.SIT):
                    b.behavior.force_state(State.WALK_RIGHT if fx_a > fx_b else State.WALK_LEFT)
            elif dist <= PROXIMITY_PX:
                self._walking_back = False
                if a.behavior._state not in (State.TALKING, State.SIT):
                    a.behavior.notify_talking(True)
                if b.behavior._state not in (State.TALKING, State.SIT):
                    b.behavior.notify_talking(True)
        except Exception:
            pass

    async def _run_conversation(self, a, b, scenario, activity,
                                 n_exchanges: int) -> None:
        from core.behavior import State
        _, sc_label, _, _, sc_desc, sc_longueur = scenario

        # Règles de longueur selon le scénario
        if sc_longueur == "courte":
            longueur_rule = "• UNE SEULE phrase maximum — sois ultra bref"
        elif sc_longueur == "longue":
            longueur_rule = "• Réponse longue et développée OBLIGATOIRE — 3-5 phrases si nécessaire\n• Si on te pose une question, réponds-y COMPLÈTEMENT avant de passer à autre chose"
        else:
            longueur_rule = "• 1-3 phrases selon ce que tu as à dire — ni trop court ni trop long"
        _, act_label, act_desc     = activity

        try:
            name_a  = a.character_name
            name_b  = b.character_name
            cfg     = self._ctrl.config
            mem     = self._ctrl.memory
            perso_a = cfg.get_personality(name_a)
            perso_b = cfg.get_personality(name_b)

            # ── Contexte relationnel ──────────────────────────────────────
            rel     = mem.get_relation(name_a, name_b)
            rel_lbl = mem.relation_label(rel["score"], rel["meetings"])
            rel_ctx = (f"Vous vous connaissez — vous êtes {rel_lbl} "
                       f"(rencontres : {rel['meetings']}). ")
            if rel["last_topic"]:
                rel_ctx += f"Dernier sujet abordé : {rel['last_topic']}. "

            # ── Se faire face ─────────────────────────────────────────────
            fx_a = a.physics.state.feet_x
            fx_b = b.physics.state.feet_x
            a.behavior.look_right = fx_a > fx_b
            b.behavior.look_right = fx_b > fx_a

            # ── Activité sociale ──────────────────────────────────────────
            await self._apply_activity(a, b, act_label)
            await asyncio.sleep(0.4)

            history: list[str] = []
            dominant_topic     = ""

            for i in range(n_exchanges):
                speaker  = a if i % 2 == 0 else b
                sp_name  = name_a if i % 2 == 0 else name_b
                li_name  = name_b if i % 2 == 0 else name_a
                sp_perso = perso_a if i % 2 == 0 else perso_b

                await self._maintain_activity(a, b, act_label)
                if a.behavior._state not in (State.TALKING, State.SIT):
                    a.behavior.notify_talking(True)
                if b.behavior._state not in (State.TALKING, State.SIT):
                    b.behavior.notify_talking(True)

                # Règles anti-répétition selon le tour
                if i == 0:
                    anti_repeat = (
                        f"• C'est le début — tu peux dire bonjour SI c'est naturel dans ce contexte"
                    )
                else:
                    anti_repeat = (
                        f"• NE PAS te présenter, NE PAS dire bonjour à nouveau — la conversation est déjà lancée\n"
                        f"• NE PAS répéter ce que {li_name} vient de dire\n"
                        f"• NE PAS poser une question si tu n'as pas encore répondu à la question précédente"
                    )

                system = (
                    f"Tu es {sp_name}. Ta personnalité : {sp_perso}\n\n"
                    f"Tu es en pleine conversation avec {li_name} ({rel_lbl}).\n"
                    f"Contexte : {sc_desc}\n\n"
                    f"RÈGLES STRICTES :\n"
                    f"{longueur_rule}\n"
                    f"{anti_repeat}\n"
                    f"• Style oral naturel — 'hm', 'ah', 'ben', '...' sont OK\n"
                    f"• Zéro *actions*, zéro guillemets, zéro narration\n"
                    f"• Parle directement à {li_name} à la première personne"
                )

                if i == 0:
                    # Premier tour — lancer la conversation sans se présenter inutilement
                    if sc_label == "salutation":
                        user_prompt = f"Lance la conversation avec {li_name} en UNE phrase de salutation naturelle."
                    elif sc_label == "question":
                        user_prompt = f"Pose UNE vraie question à {li_name} — quelque chose qui t'intéresse vraiment chez lui/elle."
                    elif sc_label == "philosophique":
                        user_prompt = f"Lance une réflexion profonde à {li_name} — quelque chose qui te tracasse sur votre existence ici."
                    elif sc_label == "dispute":
                        user_prompt = f"Lance une petite controverse avec {li_name} — dis quelque chose d'un peu provocateur sur un sujet anodin."
                    elif sc_label == "blague":
                        user_prompt = f"Lance une blague ou anecdote drôle à {li_name}."
                    else:
                        user_prompt = f"Lance la conversation avec {li_name} de façon naturelle et spontanée."
                else:
                    ctx = "\n".join(history[-4:])
                    user_prompt = (
                        f"[Conversation en cours]\n{ctx}\n\n"
                        f"Ton tour. Réponds à {li_name}."
                    )

                bubble = self._show_bubble(speaker, sp_name)
                reply  = await self._stream_to_bubble(
                    bubble, user_prompt, sp_name, system_override=system)

                if reply:
                    history.append(f"{sp_name}: {reply}")
                    if not dominant_topic and len(reply) > 10:
                        dominant_topic = reply[:60]
                elif i == 0:
                    history.append(f"{sp_name}: ...")

                # Temps d'affichage proportionnel à la longueur de la réponse
                words = len(reply.split()) if reply else 5
                linger = max(2000, min(6000, words * 300))  # 300ms/mot, 2-6s
                await asyncio.sleep(linger / 1000)
                if bubble:
                    try: bubble.fade_out(then_close=True)
                    except Exception: pass
                await asyncio.sleep(0.4)

            # ── Mettre à jour la relation ─────────────────────────────────
            score_map = {
                "salutation": +2, "au_revoir": +1, "chemin": +2,
                "discussion": +4, "commérage": +3, "question": +3,
                "philosophique": +5, "dispute": -3, "blague": +3,
            }
            delta = score_map.get(sc_label, +2)
            mem.update_relation(name_a, name_b, delta, dominant_topic)
            print(f"[Conv] {name_a}↔{name_b}: {rel['score']:.0f}→"
                  f"{rel['score']+delta:.0f} ({rel_lbl})")

            # ── Mettre à jour les humeurs ─────────────────────────────────
            from ui.mood_indicator import SCENARIO_MOODS
            mood = SCENARIO_MOODS.get(sc_label, "neutral")
            mood_b_key = "angry" if sc_label == "dispute" else mood
            for mascot, mood_key in [(a, mood), (b, mood_b_key)]:
                if hasattr(mascot, '_mood_indicator') and mascot._mood_indicator:
                    mascot._mood_indicator.set_mood(mood_key)

        except Exception as e:
            print(f"[Conv] Erreur : {e}")
        finally:
            try: a.behavior.notify_talking(False)
            except Exception: pass
            try: b.behavior.notify_talking(False)
            except Exception: pass
            self._active   = False
            self._cooldown = COOLDOWN_TICKS

    # ── Activités sociales ────────────────────────────────────────────────

    async def _apply_activity(self, a, b, act_label: str) -> None:
        """Applique l'activité sociale initiale aux deux persos."""
        from core.behavior import State
        try:
            if act_label == "assis":
                # Les deux s'assoient
                if a.behavior._has(State.SIT):
                    a.behavior.force_state(State.SIT)
                else:
                    a.behavior.notify_talking(True)
                if b.behavior._has(State.SIT):
                    b.behavior.force_state(State.SIT)
                else:
                    b.behavior.notify_talking(True)

            elif act_label == "marche":
                # Les deux marchent dans la même direction (vers le centre écran)
                a.behavior.notify_talking(True)
                b.behavior.notify_talking(True)
                # On les laisse marcher ensemble via un step target
                fx_a = a.physics.state.feet_x
                fx_b = b.physics.state.feet_x
                target = (fx_a + fx_b) / 2  # marcher l'un vers l'autre
                walk_st_a = State.WALK_RIGHT if target > fx_a else State.WALK_LEFT
                walk_st_b = State.WALK_RIGHT if target > fx_b else State.WALK_LEFT
                # Marche courte puis stop
                a.behavior.force_state(walk_st_a)
                b.behavior.force_state(walk_st_b)
                await asyncio.sleep(1.0)
                a.behavior.notify_talking(True)
                b.behavior.notify_talking(True)

            elif act_label == "un_assis":
                # A est assis, B est debout
                if a.behavior._has(State.SIT):
                    a.behavior.force_state(State.SIT)
                else:
                    a.behavior.notify_talking(True)
                b.behavior.notify_talking(True)

            else:
                # debout par défaut
                a.behavior.notify_talking(True)
                b.behavior.notify_talking(True)

        except Exception as e:
            print(f"[Conv] Activité impossible : {e}")
            a.behavior.notify_talking(True)
            b.behavior.notify_talking(True)

    async def _maintain_activity(self, a, b, act_label: str) -> None:
        """Maintient l'activité en cours (appelé à chaque échange)."""
        from core.behavior import State
        try:
            if act_label == "assis":
                if a.behavior._state not in (State.SIT, State.TALKING):
                    if a.behavior._has(State.SIT):
                        a.behavior.force_state(State.SIT)
                if b.behavior._state not in (State.SIT, State.TALKING):
                    if b.behavior._has(State.SIT):
                        b.behavior.force_state(State.SIT)
            elif act_label == "marche":
                # Petite marche synchronisée entre les échanges
                if random.random() < 0.4:  # 40% de chance de bouger
                    fx_a = a.physics.state.feet_x
                    fx_b = b.physics.state.feet_x
                    # Marcher ensemble vers un point aléatoire
                    offset = random.randint(-80, 80)
                    target_a = fx_a + offset
                    target_b = fx_b + offset
                    walk_a = State.WALK_RIGHT if offset > 0 else State.WALK_LEFT
                    walk_b = State.WALK_RIGHT if offset > 0 else State.WALK_LEFT
                    a.behavior.force_state(walk_a)
                    b.behavior.force_state(walk_b)
                    await asyncio.sleep(0.8)
                    a.behavior.notify_talking(True)
                    b.behavior.notify_talking(True)
        except Exception:
            pass

    # ── Helpers ───────────────────────────────────────────────────────────

    def _show_bubble(self, mascot, name: str):
        try:
            from ui.mascot_bubble import MascotBubble
            return MascotBubble(mascot, name)
        except Exception as e:
            print(f"[Conv] Bulle impossible : {e}")
            return None

    async def _stream_to_bubble(self, bubble, prompt: str, speaker_name: str,
                                 system_override: str = "") -> str:
        full = ""
        try:
            ai = self._ctrl.ai_client
            conv_char = f"__conv_{speaker_name}__"
            old_perso = ai.config.character_personalities.get(conv_char, "")
            if system_override:
                ai.config.character_personalities[conv_char] = system_override
            try:
                async for token in ai.stream_chat(prompt, conv_char):
                    if token.startswith("[Erreur"):
                        full = ""
                        break
                    full += token
                    if bubble:
                        try:
                            bubble.append_text(token)
                        except Exception:
                            pass
                    await asyncio.sleep(0)
            finally:
                if system_override:
                    if old_perso:
                        ai.config.character_personalities[conv_char] = old_perso
                    else:
                        ai.config.character_personalities.pop(conv_char, None)
                # Purger la mémoire __conv_ après chaque échange
                try:
                    ai.memory.clear(conv_char)
                except Exception:
                    pass
        except Exception:
            full = ""

        if not full and bubble:
            try:
                bubble.set_text("…")
            except Exception:
                pass
        return full
