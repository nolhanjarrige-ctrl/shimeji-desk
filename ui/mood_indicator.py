"""ui/mood_indicator.py — Icône d'humeur flottante au-dessus d'un mascot."""
from __future__ import annotations
import random
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QFont, QColor
from PyQt6.QtWidgets import QWidget, QApplication


# ── Humeurs disponibles ────────────────────────────────────────────────────
MOODS = {
    "happy":      ("😊", QColor(255, 220, 50),   "Heureux"),
    "excited":    ("✨", QColor(100, 220, 255),  "Enthousiaste"),
    "curious":    ("🤔", QColor(180, 140, 255),  "Curieux"),
    "tired":      ("😴", QColor(150, 180, 255),  "Fatigué"),
    "sad":        ("😔", QColor(100, 140, 220),  "Triste"),
    "angry":      ("😤", QColor(255, 100, 80),   "Énervé"),
    "love":       ("💕", QColor(255, 150, 200),  "Affectueux"),
    "neutral":    ("😐", QColor(180, 180, 200),  "Neutre"),
    "surprised":  ("😲", QColor(255, 200, 80),   "Surpris"),
    "playful":    ("😏", QColor(100, 255, 180),  "Espiègle"),
}

# Humeurs selon le score relationnel + scénario
SCENARIO_MOODS = {
    "salutation":    "happy",
    "au_revoir":     "happy",
    "chemin":        "curious",
    "discussion":    "curious",
    "commérage":     "playful",
    "question":      "curious",
    "philosophique": "curious",
    "dispute":       "angry",
    "blague":        "playful",
}

TIME_MOODS = {
    "nuit_profonde": "tired",
    "aube":          "neutral",
    "matin":         "happy",
    "midi":          "neutral",
    "après-midi":    "neutral",
    "soirée":        "happy",
    "nuit":          "tired",
}


class MoodIndicator(QWidget):
    """Petite icône d'humeur qui flotte au-dessus du mascot."""

    def __init__(self, mascot):
        super().__init__(None,
                         Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint |
                         Qt.WindowType.Tool |
                         Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._mascot  = mascot
        self._emoji   = "😊"
        self._color   = QColor(255, 220, 50)
        self._opacity = 0.0
        self._bob     = 0.0   # animation flottante
        self._bob_dir = 1

        self.resize(36, 36)

        # Repositionnement
        self._pos_timer = QTimer(self)
        self._pos_timer.timeout.connect(self._update_pos)
        self._pos_timer.start(16)

        # Animation bobbing
        self._bob_timer = QTimer(self)
        self._bob_timer.timeout.connect(self._tick_bob)
        self._bob_timer.start(50)

        # Fondu entrant
        self._fade_in_timer = QTimer(self)
        self._fade_in_timer.timeout.connect(self._fade_in_step)
        self._fade_in_timer.start(20)

        self._update_pos()
        self.show()

    def set_mood(self, mood_key: str) -> None:
        if mood_key in MOODS:
            emoji, color, _ = MOODS[mood_key]
            self._emoji = emoji
            self._color = color
            self.update()

    def fade_out_and_close(self):
        self._fade_in_timer.stop()
        self._out_timer = QTimer(self)
        self._out_timer.timeout.connect(self._fade_out_step)
        self._out_timer.start(20)

    def _fade_in_step(self):
        self._opacity = min(1.0, self._opacity + 0.07)
        self.update()
        if self._opacity >= 1.0:
            self._fade_in_timer.stop()

    def _fade_out_step(self):
        self._opacity = max(0.0, self._opacity - 0.05)
        self.update()
        if self._opacity <= 0.0:
            self._out_timer.stop()
            self.close()

    def _tick_bob(self):
        self._bob += 0.5 * self._bob_dir
        if abs(self._bob) >= 3:
            self._bob_dir *= -1
        self._update_pos()

    def _update_pos(self):
        if not self._mascot or not self._mascot.isVisible():
            return
        mpos = self._mascot.mapToGlobal(self._mascot.rect().topLeft())
        mw   = self._mascot.width()
        x = mpos.x() + mw - self.width() - 2
        y = mpos.y() - self.height() - 4 + int(self._bob)
        screen = QApplication.primaryScreen().geometry()
        x = max(screen.left(), min(x, screen.right()  - self.width()))
        y = max(screen.top(),  min(y, screen.bottom() - self.height()))
        self.move(x, y)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(self._opacity)
        p.setFont(QFont("Segoe UI Emoji", 18))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._emoji)
        p.end()
