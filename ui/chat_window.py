"""ui/chat_window.py – Interface de chat avec le personnage IA."""
from __future__ import annotations
import asyncio
from typing import Optional

from PyQt6.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QObject,
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QLabel, QFrame, QScrollArea, QSizePolicy,
)


# ── Worker thread pour l'IA (non-bloquant) ────────────────────────────

class AIWorker(QObject):
    token_received = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, ai_client, message: str, character_name: str):
        super().__init__()
        self.ai_client = ai_client
        self.message = message
        self.character_name = character_name
        self._full_reply = ""

    def run(self) -> None:
        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(self._stream())
            loop.close()
        except Exception as e:
            self.error.emit(str(e))

    async def _stream(self) -> None:
        async for token in self.ai_client.stream_chat(self.message, self.character_name):
            self._full_reply += token
            self.token_received.emit(token)
        self.finished.emit(self._full_reply)


# ── Bulle de message ──────────────────────────────────────────────────

class MessageBubble(QFrame):
    def __init__(self, text: str, role: str, parent=None):
        super().__init__(parent)
        self.role = role
        self.setFrameShape(QFrame.Shape.NoFrame)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lbl.setMaximumWidth(340)
        lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        if role == "assistant":
            lbl.setStyleSheet("""
                QLabel {
                    background: #1e1e3a;
                    color: #c8c8ff;
                    border: 1px solid #4040aa;
                    border-radius: 12px;
                    padding: 8px 12px;
                    font-size: 13px;
                }
            """)
            layout.addWidget(lbl)
            layout.addStretch()
        else:
            lbl.setStyleSheet("""
                QLabel {
                    background: #2d2d5a;
                    color: #e8e8ff;
                    border: 1px solid #6060cc;
                    border-radius: 12px;
                    padding: 8px 12px;
                    font-size: 13px;
                }
            """)
            layout.addStretch()
            layout.addWidget(lbl)

        self._label = lbl

    def append_text(self, text: str) -> None:
        self._label.setText(self._label.text() + text)


# ── Fenêtre principale de chat ─────────────────────────────────────────

class ChatWindow(QWidget):
    """
    Fenêtre de chat cyberpunk attachée au personnage.
    Supporte le streaming token-par-token.
    """

    def __init__(self, mascot_window, ai_client, config, parent=None):
        super().__init__(parent)
        self.mascot = mascot_window
        self.ai_client = ai_client
        self.config = config
        self._current_bubble: Optional[MessageBubble] = None
        self._ai_thread: Optional[QThread] = None
        self._worker: Optional[AIWorker] = None

        self._setup_ui()
        self._position_near_mascot()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(400)
        self.setMinimumHeight(300)
        self.setMaximumHeight(600)

        # Conteneur principal
        container = QFrame(self)
        container.setObjectName("container")
        container.setStyleSheet("""
            QFrame#container {
                background: rgba(10, 10, 30, 230);
                border: 1px solid #5050cc;
                border-radius: 16px;
            }
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setFixedHeight(44)
        header.setStyleSheet("background: #0d0d2a; border-radius: 16px 16px 0 0;")
        hlayout = QHBoxLayout(header)
        hlayout.setContentsMargins(12, 0, 12, 0)

        title = QLabel(f"✦ {self.config.character_name}")
        title.setStyleSheet("color: #8888ff; font-weight: bold; font-size: 13px;")
        hlayout.addWidget(title)
        hlayout.addStretch()

        btn_clear = QPushButton("🗑")
        btn_clear.setFlat(True)
        btn_clear.setToolTip("Effacer la conversation")
        btn_clear.setStyleSheet("color: #888; font-size: 14px; border: none;")
        btn_clear.clicked.connect(self._clear_history)
        hlayout.addWidget(btn_clear)

        btn_close = QPushButton("✕")
        btn_close.setFlat(True)
        btn_close.setStyleSheet("color: #888; font-size: 14px; border: none;")
        btn_close.clicked.connect(self.hide)
        hlayout.addWidget(btn_close)

        layout.addWidget(header)

        # Zone de messages (scrollable)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                width: 6px; background: #0d0d2a; border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #4040aa; border-radius: 3px;
            }
        """)

        self._msg_container = QWidget()
        self._msg_container.setStyleSheet("background: transparent;")
        self._msg_layout = QVBoxLayout(self._msg_container)
        self._msg_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._msg_layout.setSpacing(6)
        self._msg_layout.setContentsMargins(8, 8, 8, 8)
        self._msg_layout.addStretch()

        self._scroll.setWidget(self._msg_container)
        layout.addWidget(self._scroll, 1)

        # Zone de saisie
        input_frame = QFrame()
        input_frame.setStyleSheet("""
            QFrame {
                background: #0d0d2a;
                border-top: 1px solid #3030aa;
                border-radius: 0 0 16px 16px;
            }
        """)
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(10, 8, 10, 10)
        input_layout.setSpacing(8)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Écris un message…")
        self._input.setStyleSheet("""
            QLineEdit {
                background: #1a1a3a;
                color: #d0d0ff;
                border: 1px solid #4040aa;
                border-radius: 10px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QLineEdit:focus { border-color: #7070ff; }
        """)
        self._input.returnPressed.connect(self._send_message)
        input_layout.addWidget(self._input, 1)

        self._btn_send = QPushButton("➤")
        self._btn_send.setFixedSize(36, 36)
        self._btn_send.setStyleSheet("""
            QPushButton {
                background: #5050cc;
                color: white;
                border-radius: 18px;
                font-size: 16px;
                border: none;
            }
            QPushButton:hover { background: #7070ff; }
            QPushButton:pressed { background: #3030aa; }
            QPushButton:disabled { background: #333; color: #666; }
        """)
        self._btn_send.clicked.connect(self._send_message)
        input_layout.addWidget(self._btn_send)

        layout.addWidget(input_frame)

        # Message de bienvenue
        self._add_bubble(
            f"Bonjour ! Je suis {self.config.character_name}. "
            "Comment puis-je t'aider ?",
            "assistant",
        )

    # ------------------------------------------------------------------
    # Positionnement
    # ------------------------------------------------------------------

    def _position_near_mascot(self) -> None:
        if not self.mascot:
            return
        mascot_pos = self.mascot.mascot_position()
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().geometry()

        x = mascot_pos.x() - self.width() - 20
        y = mascot_pos.y()

        # Si trop à gauche, mettre à droite
        if x < screen.left():
            x = mascot_pos.x() + self.mascot.width() + 20

        # Clamp vertical
        y = max(screen.top(), min(y, screen.bottom() - self.height()))

        self.move(x, y)

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    def _add_bubble(self, text: str, role: str) -> MessageBubble:
        bubble = MessageBubble(text, role)
        # Insérer avant le stretch
        count = self._msg_layout.count()
        self._msg_layout.insertWidget(count - 1, bubble)
        QTimer.singleShot(50, self._scroll_to_bottom)
        return bubble

    def _scroll_to_bottom(self) -> None:
        sb = self._scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ------------------------------------------------------------------
    # Envoi de message
    # ------------------------------------------------------------------

    def _send_message(self) -> None:
        text = self._input.text().strip()
        if not text or self._ai_thread is not None:
            return

        self._input.clear()
        self._btn_send.setEnabled(False)
        self._add_bubble(text, "user")

        # Bulle de réponse (vide, sera remplie par streaming)
        self._current_bubble = self._add_bubble("…", "assistant")

        # Thread IA
        self._ai_thread = QThread(self)
        self._worker = AIWorker(self.ai_client, text, self.config.character_name)
        self._worker.moveToThread(self._ai_thread)

        self._ai_thread.started.connect(self._worker.run)
        self._worker.token_received.connect(self._on_token)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._ai_thread.quit)
        self._ai_thread.finished.connect(self._cleanup_thread)

        self._ai_thread.start()

    def _on_token(self, token: str) -> None:
        if self._current_bubble:
            current = self._current_bubble._label.text()
            if current == "…":
                self._current_bubble._label.setText(token)
            else:
                self._current_bubble._label.setText(current + token)
            self._scroll_to_bottom()

    def _on_finished(self, full_reply: str) -> None:
        self._current_bubble = None
        self._btn_send.setEnabled(True)
        self._input.setFocus()

    def _on_error(self, err: str) -> None:
        if self._current_bubble:
            self._current_bubble._label.setText(f"⚠ Erreur : {err}")
        self._current_bubble = None
        self._btn_send.setEnabled(True)
        self._input.setFocus()

    def _cleanup_thread(self) -> None:
        self._ai_thread = None
        self._worker = None

    # ------------------------------------------------------------------
    # Autres actions
    # ------------------------------------------------------------------

    def _clear_history(self) -> None:
        # Vider l'UI
        while self._msg_layout.count() > 1:
            item = self._msg_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        # Vider la mémoire
        if hasattr(self.ai_client, "memory"):
            self.ai_client.memory.clear(self.config.character_name)

        self._add_bubble("Mémoire effacée ! Comment puis-je t'aider ?", "assistant")

    def toggle(self) -> None:
        """Affiche/masque la fenêtre de chat."""
        if self.isVisible():
            self.hide()
        else:
            self._position_near_mascot()
            self.show()
            self._input.setFocus()
