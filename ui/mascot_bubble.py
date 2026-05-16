"""ui/mascot_bubble.py — Bulle de dialogue flottante au-dessus d'un mascot."""
from __future__ import annotations
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty, QPoint
from PyQt6.QtGui import QPainter, QColor, QFont, QPainterPath, QFontMetrics
from PyQt6.QtWidgets import QWidget, QApplication


class MascotBubble(QWidget):
    """Petite bulle de dialogue qui flotte au-dessus d'un mascot.

    - Apparaît en fondu, disparaît en fondu
    - Texte en streaming (caractère par caractère)
    - Se positionne automatiquement au-dessus du mascot
    - Style Arknights terminal
    """

    _BG       = QColor(13,  13,  26,  220)
    _BORDER   = QColor(74, 158, 255, 200)
    _TEXT     = QColor(200, 216, 255, 255)
    _NAME     = QColor(74,  158, 255, 255)
    _TAIL_H   = 12   # hauteur de la queue
    _PAD_X    = 14
    _PAD_Y    = 10
    _MAX_W    = 220  # plus étroit → se cale mieux sur le perso
    _FONT_SZ  = 11

    def __init__(self, mascot_window, character_name: str):
        super().__init__(None,
                         Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint |
                         Qt.WindowType.Tool |
                         Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._mascot   = mascot_window
        self._name     = character_name
        self._text     = ""
        self._opacity  = 0.0
        self._font     = QFont("Consolas", self._FONT_SZ)
        self._name_font = QFont("Consolas", self._FONT_SZ - 1, QFont.Weight.Bold)

        # Timer repositionnement
        self._pos_timer = QTimer(self)
        self._pos_timer.timeout.connect(self._update_pos)
        self._pos_timer.start(16)  # 60fps

        # Fondu entrant
        self._fade_timer = QTimer(self)
        self._fade_timer.timeout.connect(self._fade_in_step)
        self._fade_timer.start(16)

        self.resize(self._MAX_W + self._PAD_X * 2, 60)
        self._update_pos()
        self.show()

    # ── Opacité ───────────────────────────────────────────────────────────

    def get_opacity(self): return self._opacity
    def set_opacity(self, v):
        self._opacity = v
        self.update()
    opacity = pyqtProperty(float, get_opacity, set_opacity)

    def _fade_in_step(self):
        self._opacity = min(1.0, self._opacity + 0.08)
        self.update()
        if self._opacity >= 1.0:
            self._fade_timer.stop()

    def fade_out(self, then_close=True):
        self._fade_timer.stop()
        if hasattr(self, '_out_timer') and self._out_timer.isActive():
            return
        self._out_timer = QTimer(self)
        self._out_timer.timeout.connect(self._fade_out_step)
        self._out_timer.setProperty("then_close", then_close)
        self._out_timer.start(16)

    def _fade_out_step(self):
        self._opacity = max(0.0, self._opacity - 0.06)
        self.update()
        if self._opacity <= 0.0:
            self._out_timer.stop()
            if self._out_timer.property("then_close"):
                self.close()

    # ── Texte streaming ───────────────────────────────────────────────────

    def append_text(self, token: str):
        self._text += token
        self._relayout()
        self.update()

    def set_text(self, text: str):
        self._text = text
        self._relayout()
        self.update()

    def _relayout(self):
        fm   = QFontMetrics(self._font)
        # Calcul hauteur avec retour à la ligne
        lines = self._wrap_text(self._text, fm, self._MAX_W)
        name_h = QFontMetrics(self._name_font).height() + 4
        h = name_h + len(lines) * (fm.height() + 2) + self._PAD_Y * 2 + self._TAIL_H + 6
        h = max(h, 55)
        self.resize(self._MAX_W + self._PAD_X * 2, h)
        self._update_pos()

    def _wrap_text(self, text, fm, max_w) -> list[str]:
        if not text:
            return [""]
        words  = text.split(" ")
        lines  = []
        cur    = ""
        for w in words:
            test = (cur + " " + w).strip()
            if fm.horizontalAdvance(test) <= max_w:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines or [""]

    # ── Positionnement ────────────────────────────────────────────────────

    def _update_pos(self):
        if not self._mascot or not self._mascot.isVisible():
            return
        # Utiliser les coordonnées écran absolues (mapToGlobal)
        # pos() retourne des coords relatives au parent, pas fiable pour les top-level windows
        mpos = self._mascot.mapToGlobal(self._mascot.rect().topLeft())
        mw   = self._mascot.width()
        mh   = self._mascot.height()

        # Centré horizontalement sur le mascot, au-dessus de sa tête
        x = mpos.x() + mw // 2 - self.width() // 2
        y = mpos.y() - self.height() - 6

        # Si pas assez de place en haut → afficher en dessous
        screen = QApplication.primaryScreen().geometry()
        if y < screen.top():
            y = mpos.y() + mh + 6

        x = max(screen.left(), min(x, screen.right() - self.width()))
        y = max(screen.top(),  min(y, screen.bottom() - self.height()))
        self.move(x, y)
        self.update()  # recalculer la position de la queue

    def _get_tail_x(self) -> int:
        """Calcule la position X de la queue selon la position du mascot."""
        if not self._mascot or not self._mascot.isVisible():
            return self.width() // 2
        # Centre du mascot en coordonnées écran
        mpos   = self._mascot.mapToGlobal(self._mascot.rect().topLeft())
        mascot_cx = mpos.x() + self._mascot.width() // 2
        # Convertir en coordonnées locales de la bulle
        bpos   = self.pos()
        local_x = mascot_cx - bpos.x()
        # Clamp avec marges pour que la queue reste dans la bulle
        margin = 16
        return max(margin, min(local_x, self.width() - margin))

    # ── Rendu ─────────────────────────────────────────────────────────────

    def paintEvent(self, _event):
        if not self._text and not self._name:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(self._opacity)

        w  = self.width()
        h  = self.height() - self._TAIL_H
        r  = 10

        # Queue dynamique — pointe vers le centre du mascot
        tail_x = self._get_tail_x()

        # Fond + bordure avec queue
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, r, r)
        path.moveTo(tail_x - 8, h)
        path.lineTo(tail_x,     h + self._TAIL_H)
        path.lineTo(tail_x + 8, h)
        path.closeSubpath()

        p.fillPath(path, self._BG)
        pen = p.pen()
        pen.setColor(self._BORDER)
        pen.setWidthF(1.5)
        p.setPen(pen)
        p.drawPath(path)

        # Nom du perso
        fm_name = QFontMetrics(self._name_font)
        p.setFont(self._name_font)
        pen.setColor(self._NAME)
        p.setPen(pen)
        name_y = self._PAD_Y + fm_name.ascent()
        p.drawText(self._PAD_X, name_y, self._name)

        # Texte
        fm    = QFontMetrics(self._font)
        lines = self._wrap_text(self._text, fm, self._MAX_W)
        p.setFont(self._font)
        pen.setColor(self._TEXT)
        p.setPen(pen)
        ty = name_y + fm_name.descent() + 4 + fm.ascent()
        for line in lines:
            p.drawText(self._PAD_X, ty, line)
            ty += fm.height() + 2

        p.end()
