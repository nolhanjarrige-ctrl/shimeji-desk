"""core/system_reactor.py — Réactions des mascots à l'heure, aux événements système, et au sommeil."""
from __future__ import annotations
import asyncio
import random
from datetime import datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.mascot_controller import MascotController


_TIME_CONTEXTS = [
    (0,  5,  "nuit_profonde", [
        "Il est très tard… ou très tôt. Tu es encore là ?",
        "C'est le milieu de la nuit, tu devrais dormir.",
        "Même les fantômes dorment à cette heure-ci.",
        "Bonsoir… ou bonjour ? Je ne sais plus.",
    ]),
    (5,  8,  "aube", [
        "Le soleil se lève à peine. Tu es matinal !",
        "L'aube pointe. Une nouvelle journée commence.",
        "Il est tôt ! Tu as bien dormi ?",
        "Bonjour, le monde se réveille.",
    ]),
    (8,  12, "matin", [
        "Bonne matinée ! On commence bien la journée ?",
        "Le matin est parfait pour être productif.",
        "Tu as pris ton café ? Je compte sur toi.",
        "La journée commence, prêt pour l'aventure ?",
    ]),
    (12, 14, "midi", [
        "C'est l'heure de la pause déjeuner !",
        "Tu as pensé à manger ? C'est important.",
        "Midi ! La moitié de la journée est déjà passée.",
        "Pause déjeuner ! Tu mérites de te reposer.",
    ]),
    (14, 18, "après-midi", [
        "L'après-midi avance. Tu tiens le coup ?",
        "Encore quelques heures et c'est fini pour aujourd'hui.",
        "La journée avance bien ?",
        "Tu as besoin d'un coup de main ?",
    ]),
    (18, 21, "soirée", [
        "La journée se termine. Tu as bien travaillé ?",
        "Bonsoir ! Tu rentres bientôt ?",
        "La soirée commence, tu te détends ?",
        "Bonne soirée ! Tu mérites de te reposer.",
    ]),
    (21, 24, "nuit", [
        "Il se fait tard. Tu devrais penser à dormir.",
        "Bonne nuit bientôt ? Tu résistes encore !",
        "La nuit avance… prends soin de toi.",
        "Tu devrais aller te coucher, non ?",
    ]),
]

_SPECIAL_DAYS = {
    (1,  1):  "Bonne année ! Que cette nouvelle année soit fantastique !",
    (14, 2):  "Joyeuse Saint-Valentin ! ♥",
    (1,  4):  "Méfie-toi des poissons d'avril aujourd'hui !",
    (31, 10): "Joyeux Halloween ! Boo ! 👻",
    (25, 12): "Joyeux Noël ! 🎄 Ho ho ho !",
    (31, 12): "Dernière soirée de l'année ! Prêt pour le compte à rebours ?",
}

_SLEEP_HOUR_START = 22
_SLEEP_HOUR_END   = 6
_SLEEP_TICKS_MIN  = 30 * 60 * 20   # 20min = bien dormi
_FATIGUE_DELAY    = 30 * 60 * 5    # 5min après 22h avant de s'endormir


def _get_time_context() -> tuple[str, list[str]]:
    h = datetime.now().hour
    for start, end, label, comments in _TIME_CONTEXTS:
        if start <= h < end:
            return label, comments
    return "nuit", _TIME_CONTEXTS[0][3]


def _get_special_day() -> Optional[str]:
    now = datetime.now()
    return _SPECIAL_DAYS.get((now.day, now.month))


def _is_sleep_time() -> bool:
    h = datetime.now().hour
    return h >= _SLEEP_HOUR_START or h < _SLEEP_HOUR_END


class SystemReactor:

    def __init__(self, controller: "MascotController"):
        self._ctrl          = controller
        self._hour_cd       = 0
        self._special_cd    = 0
        self._last_hour     = -1
        self._special_shown = False
        self._sleep_states: dict[int, dict] = {}

    def tick(self, mascots: list) -> None:
        if not mascots:
            return
        if self._hour_cd > 0:
            self._hour_cd -= 1
        if self._special_cd > 0:
            self._special_cd -= 1
        now = datetime.now()

        # Jour spécial
        if not self._special_shown and self._special_cd == 0:
            msg = _get_special_day()
            if msg:
                mascot = random.choice(mascots)
                self._show_reaction(mascot, msg)
                self._special_shown = True
                self._special_cd    = 30 * 60 * 60
                return

        # Réaction horaire
        if now.hour != self._last_hour and self._hour_cd == 0:
            self._last_hour = now.hour
            if random.random() < 0.6:
                _, comments = _get_time_context()
                msg         = random.choice(comments)
                mascot      = random.choice(mascots)
                self._show_reaction(mascot, msg)
                self._hour_cd = 30 * 60 * 20

        # Gestion du sommeil
        if getattr(self._ctrl.config, 'enable_sleep', True):
            self._tick_sleep(mascots, now)

    def _tick_sleep(self, mascots: list, now: datetime) -> None:
        from core.behavior import State
        for mascot in mascots:
            mid = mascot.mascot_id
            if mid not in self._sleep_states:
                self._sleep_states[mid] = {
                    "sleeping": False, "sleep_ticks": 0,
                    "fatigue_cd": _FATIGUE_DELAY
                }
            st = self._sleep_states[mid]

            if st["sleeping"]:
                st["sleep_ticks"] += 1
                if not _is_sleep_time():
                    asyncio.ensure_future(self._wake_up(mascot, st))
                    st["sleeping"] = False
            else:
                if _is_sleep_time():
                    if st["fatigue_cd"] > 0:
                        st["fatigue_cd"] -= 1
                        if st["fatigue_cd"] == _FATIGUE_DELAY // 2:
                            self._set_mood(mascot, "tired")
                    else:
                        asyncio.ensure_future(self._fall_asleep(mascot, st))
                        st["sleeping"]    = True
                        st["sleep_ticks"] = 0
                else:
                    st["fatigue_cd"] = _FATIGUE_DELAY

    async def _fall_asleep(self, mascot, st: dict) -> None:
        from core.behavior import State
        from ui.mascot_bubble import MascotBubble
        try:
            sleepy_msgs = [
                "Zzz… je m'assoupis un peu…",
                "Je suis épuisé… bonne nuit…",
                "*bâille* Je peux dormir cinq minutes ?",
                "Mes yeux se ferment tout seuls…",
            ]
            bubble = MascotBubble(mascot, mascot.character_name)
            bubble.set_text(random.choice(sleepy_msgs))
            self._set_mood(mascot, "tired")
            await asyncio.sleep(3.0)
            bubble.fade_out(then_close=True)
            await asyncio.sleep(0.5)

            if mascot.physics.state.on_any_floor:
                has_sleep = (mascot.sprite.get_action('Sleep')
                             or mascot.sprite.get_action('Sleeping'))
                if has_sleep:
                    mascot.behavior.force_state(State.SLEEP)
        except Exception as e:
            print(f"[Sleep] Erreur endormissement : {e}")

    async def _wake_up(self, mascot, st: dict) -> None:
        from core.behavior import State
        from ui.mascot_bubble import MascotBubble
        try:
            slept_well = st["sleep_ticks"] >= _SLEEP_TICKS_MIN
            if slept_well:
                mood = "happy"
                wake_msgs = [
                    "Mmh… quelle bonne nuit ! Je suis en forme !",
                    "Ah, j'ai bien dormi. Prêt pour une nouvelle journée !",
                    "*s'étire* Je me sens super bien ce matin !",
                    "Bonne nuit derrière moi, bonne journée devant moi !",
                ]
            else:
                mood = "sad"
                wake_msgs = [
                    "Je n'ai pas assez dormi… je suis épuisé.",
                    "Cette nuit était trop courte… je bâille encore.",
                    "*grommelle* Laisse-moi dormir encore un peu…",
                    "Hmm… je suis dans les vapes ce matin.",
                ]

            bubble = MascotBubble(mascot, mascot.character_name)
            bubble.set_text(random.choice(wake_msgs))
            self._set_mood(mascot, mood)

            from PyQt6.QtCore import QTimer
            QTimer.singleShot(4000, lambda: self._close_bubble(bubble))

            st["sleep_ticks"] = 0
            st["fatigue_cd"]  = _FATIGUE_DELAY
        except Exception as e:
            print(f"[Sleep] Erreur réveil : {e}")

    def _set_mood(self, mascot, mood_key: str) -> None:
        try:
            if hasattr(mascot, '_mood_indicator') and mascot._mood_indicator:
                mascot._mood_indicator.set_mood(mood_key)
        except Exception:
            pass

    def _show_reaction(self, mascot, message: str) -> None:
        if not getattr(self._ctrl.config, "enable_bubbles", True):
            return
        try:
            from ui.mascot_bubble import MascotBubble
            from ui.mood_indicator import TIME_MOODS
            bubble = MascotBubble(mascot, mascot.character_name)
            bubble.set_text(message)
            label, _ = _get_time_context()
            self._set_mood(mascot, TIME_MOODS.get(label, "neutral"))
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(5000, lambda: self._close_bubble(bubble))
        except Exception as e:
            print(f"[SystemReactor] Erreur : {e}")

    def _close_bubble(self, bubble) -> None:
        try:
            bubble.fade_out(then_close=True)
        except Exception:
            pass

    def get_time_context_for_prompt(self) -> str:
        label, _ = _get_time_context()
        now = datetime.now()
        return f"Il est {now.strftime('%H:%M')} ({label.replace('_', ' ')}). "
