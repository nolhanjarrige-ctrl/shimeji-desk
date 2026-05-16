"""ui/profile_dialog.py — Mini-profil d'un personnage (relations, historique, personnalité)."""
from __future__ import annotations
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget,
    QWidget, QTextEdit, QScrollArea, QFrame, QPushButton,
    QFormLayout, QLineEdit,
)

_C_BG     = "#0d0d1a"
_C_BG2    = "#131326"
_C_BORDER = "#2a2a6a"
_C_ACCENT = "#4a9eff"
_C_TEXT   = "#c8d8ff"
_C_TEXT2  = "#6878aa"
_C_GREEN  = "#3dffaa"
_C_RED    = "#ff3d5a"
_C_ORANGE = "#ff9a3d"

_STYLE = f"""
QDialog, QWidget {{ background: {_C_BG}; color: {_C_TEXT}; }}
QTabBar::tab {{
    background: #0a0a18; color: {_C_TEXT2};
    padding: 6px 14px; border-radius: 5px 5px 0 0;
    border: 1px solid {_C_BORDER}; margin-right: 2px;
    font-family: 'Consolas', monospace; font-size: 11px;
}}
QTabBar::tab:selected {{ background: {_C_BG2}; color: {_C_ACCENT}; border-bottom: 2px solid {_C_ACCENT}; }}
QTextEdit {{
    background: #0a0a18; color: {_C_TEXT};
    border: 1px solid {_C_BORDER}; border-radius: 5px;
    font-family: 'Consolas', monospace; font-size: 11px; padding: 6px;
}}
QPushButton {{
    background: #1e2050; color: {_C_ACCENT};
    border: 1px solid {_C_ACCENT}; border-radius: 5px;
    padding: 5px 14px; font-family: 'Consolas', monospace;
}}
QPushButton:hover {{ background: {_C_ACCENT}; color: {_C_BG}; }}
QLabel {{ color: {_C_TEXT}; }}
QScrollArea {{ border: none; background: transparent; }}
QFrame#card {{
    background: {_C_BG2}; border: 1px solid {_C_BORDER};
    border-radius: 8px; padding: 6px;
}}
"""


def _score_color(score: float) -> str:
    if score >= 30: return _C_GREEN
    if score >= 0:  return _C_ACCENT
    if score >= -30: return _C_ORANGE
    return _C_RED


class ProfileDialog(QDialog):
    def __init__(self, mascot, controller, parent=None):
        super().__init__(parent,
                         Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint)
        self.mascot     = mascot
        self.controller = controller
        self.setStyleSheet(_STYLE)
        self.setMinimumWidth(420)
        self.setMinimumHeight(480)
        self._build()
        self._position_near_mascot()

    def _build(self):
        name = self.mascot.character_name
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(12, 10, 12, 10)

        # ── Header ─────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel(f"◈  {name}")
        title.setStyleSheet(f"color:{_C_ACCENT}; font-family:'Consolas',monospace; "
                            f"font-weight:bold; font-size:15px;")
        hdr.addWidget(title)
        hdr.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(f"border:none; color:{_C_TEXT2}; background:transparent; "
                                f"font-size:14px; padding:0;")
        close_btn.clicked.connect(self.close)
        hdr.addWidget(close_btn)
        layout.addLayout(hdr)

        # ── Tabs ───────────────────────────────────────────────────────────
        tabs = QTabWidget()
        layout.addWidget(tabs)

        tabs.addTab(self._build_relations_tab(name), "🤝 Relations")
        tabs.addTab(self._build_history_tab(name),   "💬 Historique")
        tabs.addTab(self._build_personality_tab(name), "✏ Personnalité")

    def _build_relations_tab(self, name: str) -> QWidget:
        w  = QWidget()
        vl = QVBoxLayout(w)
        vl.setSpacing(8)
        vl.setContentsMargins(8, 8, 8, 8)

        mem  = self.controller.memory
        # Récupérer toutes les relations impliquant ce perso
        try:
            rows_raw = mem.get_all_relations(name)
        except Exception:
            rows_raw = []

        if not rows_raw:
            lbl = QLabel("Aucune relation enregistrée.\nApproche un autre personnage pour créer des liens !")
            lbl.setStyleSheet(f"color:{_C_TEXT2}; font-style:italic;")
            lbl.setWordWrap(True)
            vl.addWidget(lbl)
            vl.addStretch()
            return w

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setSpacing(6)

        for row in rows_raw:
            char_a    = row["char_a"]
            char_b    = row["char_b"]
            score     = row["score"]
            meetings  = row["meetings"]
            last_topic = row["last_topic"]
            other = char_b if char_a == name else char_a
            label = mem.relation_label(score, meetings)
            color = _score_color(score)

            card = QFrame()
            card.setObjectName("card")
            cl2 = QVBoxLayout(card)
            cl2.setSpacing(2)
            cl2.setContentsMargins(10, 8, 10, 8)

            row1 = QHBoxLayout()
            name_lbl = QLabel(f"<b>{other}</b>")
            name_lbl.setStyleSheet(f"color:{_C_TEXT}; font-family:'Consolas',monospace;")
            score_lbl = QLabel(f"{score:+.0f}")
            score_lbl.setStyleSheet(f"color:{color}; font-family:'Consolas',monospace; font-weight:bold;")
            row1.addWidget(name_lbl)
            row1.addStretch()
            row1.addWidget(score_lbl)
            cl2.addLayout(row1)

            rel_lbl = QLabel(f"  {label}  ·  {meetings} rencontre{'s' if meetings > 1 else ''}")
            rel_lbl.setStyleSheet(f"color:{_C_TEXT2}; font-size:10px; font-family:'Consolas',monospace;")
            cl2.addWidget(rel_lbl)

            if last_topic:
                topic_lbl = QLabel(f"  💬 {last_topic[:80]}{'…' if len(last_topic)>80 else ''}")
                topic_lbl.setStyleSheet(f"color:{_C_TEXT2}; font-size:10px; font-style:italic;")
                topic_lbl.setWordWrap(True)
                cl2.addWidget(topic_lbl)

            cl.addWidget(card)

        cl.addStretch()
        scroll.setWidget(content)
        vl.addWidget(scroll)
        return w

    def _build_history_tab(self, name: str) -> QWidget:
        w  = QWidget()
        vl = QVBoxLayout(w)
        vl.setContentsMargins(8, 8, 8, 8)

        mem = self.controller.memory
        try:
            msgs = mem.get_recent_messages(name, n=40)
            summary = mem.get_latest_summary(name)
        except Exception:
            msgs, summary = [], None

        txt = QTextEdit()
        txt.setReadOnly(True)

        content = ""
        if summary:
            content += f"── Résumé ──\n{summary}\n\n── Récent ──\n"
        if msgs:
            for m in msgs:
                role  = "Toi" if m["role"] == "user" else name
                color = _C_ACCENT if m["role"] == "assistant" else _C_TEXT2
                content += f'<span style="color:{color}"><b>{role}</b></span> : {m["content"]}<br>'
        else:
            content = f'<span style="color:{_C_TEXT2}"><i>Aucun historique pour {name}.</i></span>'

        txt.setHtml(content)
        vl.addWidget(txt)

        clear_btn = QPushButton("🗑  Effacer l'historique")
        clear_btn.clicked.connect(lambda: self._clear_history(name, txt))
        vl.addWidget(clear_btn)
        return w

    def _clear_history(self, name: str, txt: QTextEdit):
        self.controller.memory.clear(name)
        txt.setHtml(f'<span style="color:{_C_TEXT2}"><i>Historique effacé.</i></span>')

    def _build_personality_tab(self, name: str) -> QWidget:
        w  = QWidget()
        vl = QVBoxLayout(w)
        vl.setContentsMargins(8, 8, 8, 8)
        vl.setSpacing(8)

        cfg = self.controller.config
        lbl = QLabel(f"Personnalité de {name} :")
        lbl.setStyleSheet(f"color:{_C_TEXT2}; font-size:11px;")
        vl.addWidget(lbl)

        self._perso_edit = QTextEdit()
        self._perso_edit.setPlainText(cfg.get_personality(name))
        vl.addWidget(self._perso_edit)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("💾  Sauvegarder")
        save_btn.clicked.connect(lambda: self._save_personality(name))
        regen_btn = QPushButton("🔄  Régénérer via IA")
        regen_btn.clicked.connect(lambda: self._regen_personality(name))
        btn_row.addWidget(save_btn)
        btn_row.addWidget(regen_btn)
        vl.addLayout(btn_row)
        return w

    def _save_personality(self, name: str):
        text = self._perso_edit.toPlainText().strip()
        self.controller.config.set_personality(name, text)
        self.controller.config.save()

    def _regen_personality(self, name: str):
        """Régénère la personnalité via IA en préservant l'ancienne si échec."""
        import asyncio
        self._old_perso = self.controller.config.character_personalities.get(name, "")
        self._perso_edit.setPlainText("⏳ Génération en cours...")
        asyncio.ensure_future(self._regen_async(name))

    async def _regen_async(self, name: str):
        if name in self.controller.config.character_personalities:
            del self.controller.config.character_personalities[name]
        await self.controller._auto_personality(name)
        new_perso = self.controller.config.get_personality(name)
        if not new_perso and getattr(self, '_old_perso', ''):
            self.controller.config.set_personality(name, self._old_perso)
            new_perso = self._old_perso
        try:
            self._perso_edit.setPlainText(new_perso or "")
        except Exception:
            pass

    def _position_near_mascot(self):
        try:
            from PyQt6.QtWidgets import QApplication
            mpos = self.mascot.mapToGlobal(self.mascot.rect().topLeft())
            screen = QApplication.primaryScreen().geometry()
            x = mpos.x() - self.minimumWidth() - 10
            y = mpos.y()
            x = max(screen.left(), min(x, screen.right()  - self.minimumWidth()))
            y = max(screen.top(),  min(y, screen.bottom() - self.height()))
            self.move(x, y)
        except Exception:
            pass

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and hasattr(self, '_drag_pos'):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
