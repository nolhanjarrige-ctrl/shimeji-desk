"""ui/character_selector.py – Sélecteur de personnages style Shimeji-ee."""
from __future__ import annotations
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QDialog, QGridLayout, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QScrollArea, QWidget,
    QCheckBox, QFrame,
)


class CharacterCard(QFrame):
    """Carte cliquable pour un personnage."""

    toggled = pyqtSignal(str, bool)   # (path, selected)

    CARD_W = 240
    CARD_H = 130

    def __init__(self, char_path: Path, parent=None):
        super().__init__(parent)
        self.char_path = char_path
        self._selected = False

        self.setFixedSize(self.CARD_W, self.CARD_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet("""
            CharacterCard {
                border: 2px solid #333;
                border-radius: 8px;
                background: #111;
            }
            CharacterCard:hover {
                border: 2px solid #5555cc;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Image de portrait
        self._img_label = QLabel()
        self._img_label.setFixedSize(self.CARD_W, self.CARD_H)
        self._img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img_label.setScaledContents(False)

        # Charger chara.png ou fallback
        portrait = self._find_portrait()
        if portrait:
            pm = QPixmap(str(portrait))
            pm = pm.scaled(
                self.CARD_W, self.CARD_H,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            # Crop au centre
            if pm.width() > self.CARD_W or pm.height() > self.CARD_H:
                x = (pm.width()  - self.CARD_W) // 2
                y = (pm.height() - self.CARD_H) // 2
                pm = pm.copy(x, y, self.CARD_W, self.CARD_H)
            self._img_label.setPixmap(pm)
        else:
            self._img_label.setText("?")
            self._img_label.setStyleSheet("color: #888; font-size: 32px;")

        layout.addWidget(self._img_label)

        # Overlay nom + checkbox (en bas de la carte)
        overlay = QWidget(self._img_label)
        overlay.setGeometry(0, self.CARD_H - 36, self.CARD_W, 36)
        overlay.setStyleSheet("background: rgba(0,0,0,180);")

        row = QHBoxLayout(overlay)
        row.setContentsMargins(10, 4, 10, 4)

        name_lbl = QLabel(self.char_path.name)
        name_lbl.setStyleSheet("color: white; font-weight: bold; font-size: 13px;")
        row.addWidget(name_lbl)
        row.addStretch()

        self._check = QCheckBox()
        self._check.setStyleSheet("""
            QCheckBox::indicator { width: 18px; height: 18px; }
            QCheckBox::indicator:unchecked { border: 2px solid #888; border-radius: 4px; background: transparent; }
            QCheckBox::indicator:checked   { border: 2px solid #88f; border-radius: 4px; background: #5555cc; }
        """)
        self._check.toggled.connect(self._on_check)
        row.addWidget(self._check)

        # Sélection initiale cochée par défaut
        self._check.blockSignals(True)
        self._check.setChecked(False)
        self._check.blockSignals(False)

    def _find_portrait(self) -> Optional[Path]:
        for name in ["chara.png", "default.png", "shime1.png", "shime1.PNG"]:
            p = self.char_path / name
            if p.exists():
                return p
        # Fallback : premier PNG
        pngs = sorted(self.char_path.glob("*.png")) + sorted(self.char_path.glob("*.PNG"))
        return pngs[0] if pngs else None

    def mousePressEvent(self, event) -> None:
        self._check.setChecked(not self._check.isChecked())

    def _on_check(self, checked: bool) -> None:
        self._selected = checked
        border = "#88aaff" if checked else "#333"
        self.setStyleSheet(f"""
            CharacterCard {{
                border: 2px solid {border};
                border-radius: 8px;
                background: {"#1a1a3a" if checked else "#111"};
            }}
            CharacterCard:hover {{ border: 2px solid #5555cc; }}
        """)
        self.toggled.emit(str(self.char_path), checked)

    @property
    def selected(self) -> bool:
        return self._selected


class CharacterSelectorDialog(QDialog):
    """
    Dialogue de sélection de personnages — style Shimeji-ee Image Set Chooser.
    """

    def __init__(self, available_chars: list[Path], parent=None):
        super().__init__(parent)
        self.available_chars = available_chars
        self._selected: set[str] = set()
        self._cards: list[CharacterCard] = []

        self.setWindowTitle("Shimeji Desk – Choisir les personnages")
        self.setMinimumSize(530, 600)
        self.setMaximumSize(900, 800)
        self.setStyleSheet("""
            QDialog { background: #0d0d1a; color: #d0d0ff; }
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                width: 8px; background: #111; border-radius: 4px;
            }
            QScrollBar::handle:vertical { background: #4040aa; border-radius: 4px; }
            QPushButton {
                border-radius: 6px; padding: 8px 20px;
                font-size: 13px; font-weight: bold; border: none;
            }
        """)

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setFixedHeight(52)
        header.setStyleSheet("background: #0a0a1f; border-bottom: 1px solid #2a2a5a;")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 0, 20, 0)

        icon_lbl = QLabel("🐾")
        icon_lbl.setStyleSheet("font-size: 22px;")
        hl.addWidget(icon_lbl)

        title = QLabel("Choisir les personnages")
        title.setStyleSheet("color: #aaaaff; font-size: 15px; font-weight: bold;")
        hl.addWidget(title)
        hl.addStretch()

        count_lbl = QLabel(f"{len(self.available_chars)} personnages disponibles")
        count_lbl.setStyleSheet("color: #666; font-size: 12px;")
        hl.addWidget(count_lbl)

        layout.addWidget(header)

        # Grille scrollable
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content.setStyleSheet("background: #0d0d1a;")
        grid = QGridLayout(content)
        grid.setContentsMargins(16, 16, 16, 16)
        grid.setSpacing(12)

        COLS = 2
        for i, char_path in enumerate(self.available_chars):
            card = CharacterCard(char_path)
            card.toggled.connect(self._on_card_toggled)
            self._cards.append(card)
            grid.addWidget(card, i // COLS, i % COLS)

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        # Footer
        footer = QFrame()
        footer.setFixedHeight(60)
        footer.setStyleSheet("background: #0a0a1f; border-top: 1px solid #2a2a5a;")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(20, 0, 20, 0)

        btn_clear = QPushButton("Tout décocher")
        btn_clear.setStyleSheet("background: #2a2a4a; color: #aaa;")
        btn_clear.clicked.connect(self._clear_all)
        fl.addWidget(btn_clear)

        btn_all = QPushButton("Tout sélectionner")
        btn_all.setStyleSheet("background: #2a2a4a; color: #aaa;")
        btn_all.clicked.connect(self._select_all)
        fl.addWidget(btn_all)

        fl.addStretch()

        btn_use = QPushButton("✦ Utiliser la sélection")
        btn_use.setStyleSheet("""
            QPushButton { background: #5050cc; color: white; min-width: 180px; }
            QPushButton:hover { background: #7070ff; }
            QPushButton:pressed { background: #3030aa; }
        """)
        btn_use.clicked.connect(self.accept)
        fl.addWidget(btn_use)

        layout.addWidget(footer)

    def _on_card_toggled(self, path: str, selected: bool) -> None:
        if selected:
            self._selected.add(path)
        else:
            self._selected.discard(path)

    def _clear_all(self) -> None:
        for card in self._cards:
            card._check.setChecked(False)

    def _select_all(self) -> None:
        for card in self._cards:
            card._check.setChecked(True)

    def selected_paths(self) -> list[Path]:
        return [Path(p) for p in self._selected]
