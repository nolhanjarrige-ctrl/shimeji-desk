"""ui/tray_icon.py – System tray Shimeji Desk — design Arknights terminal."""
from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QPixmap, QColor, QPainter, QFont
from PyQt6.QtWidgets import (
    QSystemTrayIcon, QMenu, QApplication, QDialog,
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QDialogButtonBox, QDoubleSpinBox, QSpinBox, QGroupBox,
    QFormLayout, QTextEdit, QTabWidget, QWidget,
    QCheckBox, QSlider, QWidgetAction,
)

if TYPE_CHECKING:
    from core.mascot_controller import MascotController

from pathlib import Path as _P_root
_APP_ROOT = _P_root(__file__).resolve().parent.parent

# ── Palette Arknights Terminal ─────────────────────────────────────────────
_C_BG       = "#0d0d1a"   # fond très sombre
_C_BG2      = "#131326"   # fond menu
_C_BORDER   = "#2a2a6a"   # bordure
_C_ACCENT   = "#4a9eff"   # bleu Arknights
_C_ACCENT2  = "#ff6a3d"   # orange accent
_C_TEXT     = "#c8d8ff"   # texte principal
_C_TEXT2    = "#6878aa"   # texte secondaire
_C_HOVER    = "#1e2050"   # hover
_C_SUCCESS  = "#3dffaa"   # vert succès
_C_DANGER   = "#ff3d5a"   # rouge danger

_MENU_STYLE = f"""
QMenu {{
    background: {_C_BG2};
    color: {_C_TEXT};
    border: 1px solid {_C_BORDER};
    border-radius: 10px;
    padding: 6px 4px;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 13px;
}}
QMenu::item {{
    padding: 7px 22px 7px 14px;
    border-radius: 5px;
    margin: 1px 4px;
}}
QMenu::item:selected {{
    background: {_C_HOVER};
    color: {_C_ACCENT};
}}
QMenu::item:disabled {{
    color: {_C_TEXT2};
}}
QMenu::separator {{
    height: 1px;
    background: {_C_BORDER};
    margin: 5px 10px;
}}
"""

_SETTINGS_STYLE = f"""
QDialog, QTabWidget, QWidget {{ background: {_C_BG}; color: {_C_TEXT}; }}
QTabBar::tab {{
    background: #0a0a18; color: {_C_TEXT2};
    padding: 7px 18px; border-radius: 6px 6px 0 0;
    border: 1px solid {_C_BORDER}; margin-right: 2px;
    font-family: 'Consolas', monospace; font-size: 12px;
}}
QTabBar::tab:selected {{ background: {_C_BG2}; color: {_C_ACCENT}; border-bottom: 2px solid {_C_ACCENT}; }}
QGroupBox {{
    border: 1px solid {_C_BORDER}; border-radius: 8px;
    margin-top: 20px; color: {_C_ACCENT}; font-weight: bold;
    font-family: 'Consolas', monospace; font-size: 12px;
    padding-top: 8px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    background: {_C_BG};
    color: {_C_ACCENT};
    font-size: 13px;
    font-weight: bold;
    letter-spacing: 1px;
}}
QLabel {{ color: {_C_TEXT}; font-size: 12px; }}
QLineEdit, QComboBox, QTextEdit, QSpinBox, QDoubleSpinBox {{
    background: #0a0a18; color: {_C_TEXT};
    border: 1px solid {_C_BORDER}; border-radius: 5px; padding: 5px 8px;
    font-family: 'Consolas', monospace;
}}
QLineEdit:focus, QComboBox:focus {{ border-color: {_C_ACCENT}; }}
QPushButton {{
    background: {_C_HOVER}; color: {_C_ACCENT};
    border: 1px solid {_C_ACCENT}; border-radius: 5px;
    padding: 6px 18px; font-family: 'Consolas', monospace;
}}
QPushButton:hover {{ background: {_C_ACCENT}; color: {_C_BG}; }}
QPushButton#danger {{ border-color: {_C_DANGER}; color: {_C_DANGER}; }}
QPushButton#danger:hover {{ background: {_C_DANGER}; color: white; }}
QCheckBox {{ color: {_C_TEXT}; spacing: 8px; font-size: 12px; }}
QCheckBox::indicator {{
    width: 15px; height: 15px;
    border: 1px solid {_C_BORDER}; border-radius: 3px; background: #0a0a18;
}}
QCheckBox::indicator:checked {{ background: {_C_ACCENT}; border-color: {_C_ACCENT}; }}
QSlider::groove:horizontal {{ background: #0a0a18; height: 5px; border-radius: 3px; border: 1px solid {_C_BORDER}; }}
QSlider::handle:horizontal {{
    background: {_C_ACCENT}; width: 13px; height: 13px;
    border-radius: 7px; margin: -5px 0;
}}
QSlider::sub-page:horizontal {{ background: {_C_ACCENT}; border-radius: 3px; opacity: 0.4; }}
QScrollArea {{ border: none; }}
"""


def _make_tray_icon() -> QIcon:
    pm = QPixmap(32, 32)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    # Fond hexagonal stylisé
    p.setBrush(QColor(_C_BG2))
    p.setPen(QColor(_C_ACCENT))
    p.drawRoundedRect(2, 2, 28, 28, 6, 6)
    # Lettre S
    p.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
    p.setPen(QColor(_C_ACCENT))
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "S")
    p.end()
    return QIcon(pm)


# ─────────────────────────────────────────────────────────────────────────────
# Widget titre du menu
# ─────────────────────────────────────────────────────────────────────────────

class _MenuHeader(QWidget):
    def __init__(self, controller):
        super().__init__()
        self._controller = controller
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 6)
        layout.setSpacing(2)

        # Titre
        title = QLabel("◈ SHIMEJI DESK")
        title.setStyleSheet(f"color: {_C_ACCENT}; font-family: 'Consolas', monospace; font-weight: bold; font-size: 13px;")
        layout.addWidget(title)

        # Compteur mascots
        self._lbl_count = QLabel()
        self._lbl_count.setStyleSheet(f"color: {_C_TEXT2}; font-family: 'Consolas', monospace; font-size: 11px;")
        layout.addWidget(self._lbl_count)
        self._refresh()

        # Timer pour rafraîchir le compteur
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(1000)

    def _refresh(self):
        n = len(self._controller.mascots)
        self._lbl_count.setText(f"  {n} personnage{'s' if n > 1 else ''} actif{'s' if n > 1 else ''}")


# ─────────────────────────────────────────────────────────────────────────────
# SettingsDialog
# ─────────────────────────────────────────────────────────────────────────────

class SettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Paramètres — Shimeji Desk")
        self.setMinimumWidth(660)
        self.resize(680, 540)
        self.setStyleSheet(_SETTINGS_STYLE)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(0)

        # Header
        hdr = QLabel("◈ SHIMEJI DESK — Paramètres")
        hdr.setStyleSheet(f"color: {_C_ACCENT}; font-family: 'Consolas', monospace; font-weight: bold; font-size: 14px; padding: 8px 0 12px 4px;")
        layout.addWidget(hdr)

        tabs = QTabWidget()
        layout.addWidget(tabs)

        # ── Onglet IA ──────────────────────────────────────────────────────
        tab_ai = QWidget()
        vai = QVBoxLayout(tab_ai)
        vai.setSpacing(8)
        vai.setContentsMargins(12, 12, 12, 12)

        # Sélecteur de backend
        row_be = QHBoxLayout()
        row_be.addWidget(QLabel("Backend :"))
        self.cmb_backend = QComboBox()
        self.cmb_backend.addItems([
            "ollama", "lm_studio", "openrouter", "xai", "anthropic", "gemini", "custom"
        ])
        self.cmb_backend.setCurrentText(self.config.ai_backend)
        row_be.addWidget(self.cmb_backend)
        row_be.addStretch()
        vai.addLayout(row_be)

        # Sous-tabs par backend
        self._ai_tabs = QTabWidget()
        self._ai_tabs.setStyleSheet("""
            QTabBar::tab { padding: 4px 10px; font-size: 11px; }
        """)

        def _pw(label, val, echo=False):
            w = QLineEdit(val or "")
            if echo: w.setEchoMode(QLineEdit.EchoMode.Password)
            return w

        # Ollama
        t_ol = QWidget(); f_ol = QFormLayout(t_ol); f_ol.setSpacing(6)
        self.txt_ollama_url   = _pw("", self.config.ollama_url)
        self.txt_ollama_model = _pw("", self.config.ollama_model)
        f_ol.addRow("URL :",    self.txt_ollama_url)
        f_ol.addRow("Modèle :", self.txt_ollama_model)
        f_ol.addRow("", QLabel("<small style='color:#6878aa'>Ex: mistral-nemo, llama3, gemma3</small>"))
        self._ai_tabs.addTab(t_ol, "🦙 Ollama")

        # LM Studio
        t_lms = QWidget(); f_lms = QFormLayout(t_lms); f_lms.setSpacing(6)
        self.txt_lms_url   = _pw("", self.config.lm_studio_url)
        self.txt_lms_model = _pw("", self.config.lm_studio_model)
        f_lms.addRow("URL :",    self.txt_lms_url)
        f_lms.addRow("Modèle :", self.txt_lms_model)
        f_lms.addRow("", QLabel("<small style='color:#6878aa'>LM Studio doit être lancé avec server activé</small>"))
        self._ai_tabs.addTab(t_lms, "🖥 LM Studio")

        # OpenRouter
        t_or = QWidget(); f_or = QFormLayout(t_or); f_or.setSpacing(6)
        self.txt_or_key   = _pw("", self.config.openrouter_api_key, echo=True)
        self.txt_or_model = _pw("", self.config.openrouter_model)
        f_or.addRow("Clé API :", self.txt_or_key)
        f_or.addRow("Modèle :",  self.txt_or_model)
        f_or.addRow("", QLabel("<small style='color:#6878aa'>Ex: openai/gpt-4o-mini, mistralai/mistral-7b</small>"))
        self._ai_tabs.addTab(t_or, "🌐 OpenRouter")

        # xAI / Grok
        t_xai = QWidget(); f_xai = QFormLayout(t_xai); f_xai.setSpacing(6)
        self.txt_xai_key   = _pw("", self.config.xai_api_key, echo=True)
        self.txt_xai_model = _pw("", self.config.xai_model)
        f_xai.addRow("Clé API :", self.txt_xai_key)
        f_xai.addRow("Modèle :",  self.txt_xai_model)
        f_xai.addRow("", QLabel("<small style='color:#6878aa'>Ex: grok-3-mini, grok-3</small>"))
        self._ai_tabs.addTab(t_xai, "⚡ xAI / Grok")

        # Anthropic / Claude
        t_ant = QWidget(); f_ant = QFormLayout(t_ant); f_ant.setSpacing(6)
        self.txt_ant_key   = _pw("", self.config.anthropic_api_key, echo=True)
        self.txt_ant_model = _pw("", self.config.anthropic_model)
        f_ant.addRow("Clé API :", self.txt_ant_key)
        f_ant.addRow("Modèle :",  self.txt_ant_model)
        f_ant.addRow("", QLabel("<small style='color:#6878aa'>Ex: claude-sonnet-4-5, claude-opus-4-5</small>"))
        self._ai_tabs.addTab(t_ant, "🔵 Claude")

        # Gemini
        t_gem = QWidget(); f_gem = QFormLayout(t_gem); f_gem.setSpacing(6)
        self.txt_gem_key   = _pw("", self.config.gemini_api_key, echo=True)
        self.txt_gem_model = _pw("", self.config.gemini_model)
        f_gem.addRow("Clé API :", self.txt_gem_key)
        f_gem.addRow("Modèle :",  self.txt_gem_model)
        f_gem.addRow("", QLabel("<small style='color:#6878aa'>Ex: gemini-2.0-flash, gemini-1.5-pro</small>"))
        self._ai_tabs.addTab(t_gem, "✨ Gemini")

        # Custom
        t_cus = QWidget(); f_cus = QFormLayout(t_cus); f_cus.setSpacing(6)
        self.txt_cus_url   = _pw("", self.config.custom_base_url)
        self.txt_cus_key   = _pw("", self.config.custom_api_key, echo=True)
        self.txt_cus_model = _pw("", self.config.custom_model)
        f_cus.addRow("URL base :", self.txt_cus_url)
        f_cus.addRow("Clé API :",  self.txt_cus_key)
        f_cus.addRow("Modèle :",   self.txt_cus_model)
        f_cus.addRow("", QLabel("<small style='color:#6878aa'>Tout endpoint OpenAI-compatible (LocalAI, vLLM…)</small>"))
        self._ai_tabs.addTab(t_cus, "🔧 Custom")

        # Synchro onglet AI avec sélecteur backend
        _be_to_tab = {
            "ollama":0,"lm_studio":1,"openrouter":2,"xai":3,
            "anthropic":4,"gemini":5,"custom":6
        }
        self._ai_tabs.setCurrentIndex(_be_to_tab.get(self.config.ai_backend, 0))
        self.cmb_backend.currentTextChanged.connect(
            lambda b: self._ai_tabs.setCurrentIndex(_be_to_tab.get(b, 0)))
        self._ai_tabs.currentChanged.connect(
            lambda i: self.cmb_backend.setCurrentIndex(i))

        vai.addWidget(self._ai_tabs)
        tabs.addTab(tab_ai, "🤖 IA")

        # ── Onglet Personnage ──────────────────────────────────────────────
        tab_char = QWidget()
        vc = QVBoxLayout(tab_char)
        vc.setSpacing(8)
        vc.setContentsMargins(12, 12, 12, 12)

        row_scale = QHBoxLayout()
        row_scale.addWidget(QLabel("Échelle sprites :"))
        self.spn_scale = QDoubleSpinBox()
        self.spn_scale.setRange(0.5, 3.0); self.spn_scale.setSingleStep(0.1)
        self.spn_scale.setValue(self.config.mascot_scale)
        row_scale.addWidget(self.spn_scale)
        row_scale.addStretch()
        vc.addLayout(row_scale)

        vc.addWidget(QLabel("Personnalités par personnage :"))

        img_root = _APP_ROOT / "assets" / "default" / "img"
        self._char_names = sorted([
            d.name for d in img_root.iterdir()
            if d.is_dir()
            and (d / "conf" / "actions.xml").exists()
            and any(d.glob("*.png"))
        ]) if img_root.exists() else []

        row_sel = QHBoxLayout()
        row_sel.addWidget(QLabel("Personnage :"))
        self.cmb_char = QComboBox()
        self.cmb_char.addItems(self._char_names)
        self.cmb_char.setCurrentText(self.config.character_name)
        row_sel.addWidget(self.cmb_char)
        row_sel.addStretch()
        vc.addLayout(row_sel)

        vc.addWidget(QLabel("Personnalité (pour ce personnage) :"))
        self.txt_personality = QTextEdit()
        self.txt_personality.setMinimumHeight(100)
        self._load_personality_for(self.cmb_char.currentText())
        self.cmb_char.currentTextChanged.connect(self._on_char_changed)
        vc.addWidget(self.txt_personality)

        vc.addWidget(QLabel("Personnalité par défaut :"))
        self.txt_default_personality = QTextEdit(self.config.character_personality)
        self.txt_default_personality.setMinimumHeight(55)
        vc.addWidget(self.txt_default_personality)
        tabs.addTab(tab_char, "🎭 Personnage")

        # ── Onglet Comportements ───────────────────────────────────────────
        tab_beh = QWidget()
        vb = QVBoxLayout(tab_beh)
        vb.setSpacing(10)
        vb.setContentsMargins(12, 12, 12, 12)

        grp_tog = QGroupBox("Activer / Désactiver")
        fg = QVBoxLayout(grp_tog)
        fg.setSpacing(6)
        self.chk_walk_ie  = QCheckBox("WalkWithIE — porter une fenêtre en marchant")
        self.chk_walk_ie.setChecked(getattr(self.config, 'enable_walk_with_ie', True))
        self.chk_throw_ie = QCheckBox("ThrowIE — lancer une fenêtre")
        self.chk_throw_ie.setChecked(getattr(self.config, 'enable_throw_ie', True))
        self.chk_jump     = QCheckBox("Jump — sauter vers les murs / fenêtres")
        self.chk_jump.setChecked(getattr(self.config, 'enable_jump', True))
        self.chk_special  = QCheckBox("Special — animations spéciales (épées, portail…)")
        self.chk_special.setChecked(getattr(self.config, 'enable_special', True))
        for chk in [self.chk_walk_ie, self.chk_throw_ie, self.chk_jump, self.chk_special]:
            fg.addWidget(chk)
        vb.addWidget(grp_tog)

        grp_freq = QGroupBox("Fréquence globale des comportements")
        ff = QFormLayout(grp_freq)
        self.sld_freq = QSlider(Qt.Orientation.Horizontal)
        self.sld_freq.setRange(25, 200); self.sld_freq.setTickInterval(25)
        self.sld_freq.setValue(int(getattr(self.config, 'behavior_freq_scale', 1.0) * 100))
        self.lbl_freq = QLabel(f"{self.sld_freq.value()}%")
        self.sld_freq.valueChanged.connect(lambda v: self.lbl_freq.setText(f"{v}%"))
        ff.addRow("Fréquence :", self.sld_freq)
        ff.addRow("",            self.lbl_freq)
        vb.addWidget(grp_freq)
        vb.addStretch()
        tabs.addTab(tab_beh, "⚙ Comportements")

        # ── Onglet Social & Mémoire ────────────────────────────────────────
        tab_social = QWidget()
        vs = QVBoxLayout(tab_social)
        vs.setSpacing(10)
        vs.setContentsMargins(12, 12, 12, 12)

        grp_social = QGroupBox("Interactions entre personnages")
        fs = QVBoxLayout(grp_social)
        fs.setSpacing(6)
        self.chk_conversations = QCheckBox("💬  Conversations automatiques entre persos")
        self.chk_conversations.setChecked(getattr(self.config, 'enable_conversations', True))
        self.chk_bubbles = QCheckBox("🗨  Bulles de dialogue")
        self.chk_bubbles.setChecked(getattr(self.config, 'enable_bubbles', True))
        self.chk_mood = QCheckBox("😊  Indicateurs d'humeur (icônes flottantes)")
        self.chk_mood.setChecked(getattr(self.config, 'enable_mood_indicator', True))
        self.chk_minigames = QCheckBox("🎮  Mini-jeux (pierre-feuille-ciseaux)")
        self.chk_minigames.setChecked(getattr(self.config, 'enable_minigames', True))
        self.chk_sleep = QCheckBox("😴  Cycle sommeil / réveil automatique (22h–6h)")
        self.chk_sleep.setChecked(getattr(self.config, 'enable_sleep', True))
        self.chk_system_react = QCheckBox("🕐  Réactions à l'heure et aux jours spéciaux")
        self.chk_system_react.setChecked(getattr(self.config, 'enable_system_reactions', True))
        for chk in [self.chk_conversations, self.chk_bubbles, self.chk_mood,
                    self.chk_minigames, self.chk_sleep, self.chk_system_react]:
            fs.addWidget(chk)
        vs.addWidget(grp_social)

        grp_mem = QGroupBox("Mémoire & IA")
        fm = QFormLayout(grp_mem)
        fm.setSpacing(8)
        self.chk_memory = QCheckBox("Sauvegarder l'historique des conversations")
        self.chk_memory.setChecked(getattr(self.config, 'enable_memory', True))
        self.chk_summary = QCheckBox("Résumés automatiques (toutes les 40 messages)")
        self.chk_summary.setChecked(getattr(self.config, 'enable_summary', True))
        self.chk_summary.setEnabled(self.chk_memory.isChecked())
        self.chk_memory.toggled.connect(self.chk_summary.setEnabled)

        note = QLabel("⚠ Désactiver la mémoire efface l'historique à chaque session.")
        note.setStyleSheet(f"color:{_C_TEXT2}; font-size:10px;")
        note.setWordWrap(True)

        self.spn_max_msgs = QSpinBox()
        self.spn_max_msgs.setRange(10, 500)
        self.spn_max_msgs.setValue(getattr(self.config, 'memory_max_messages', 50))
        self.spn_max_msgs.setSuffix(" messages")
        self.spn_max_msgs.setEnabled(self.chk_memory.isChecked())
        self.chk_memory.toggled.connect(self.spn_max_msgs.setEnabled)

        fm.addRow("", self.chk_memory)
        fm.addRow("", self.chk_summary)
        fm.addRow("", note)
        fm.addRow("Historique max :", self.spn_max_msgs)
        vs.addWidget(grp_mem)
        vs.addStretch()
        tabs.addTab(tab_social, "🤝 Social & Mémoire")

        # ── Onglet Physique ────────────────────────────────────────────────
        tab_phys = QWidget()
        form_phys = QFormLayout(tab_phys)
        form_phys.setSpacing(10)
        form_phys.setContentsMargins(12, 12, 12, 12)
        self.spn_walk = QDoubleSpinBox()
        self.spn_walk.setRange(0.5, 15.0); self.spn_walk.setSingleStep(0.5)
        self.spn_walk.setValue(self.config.walk_speed)
        self.spn_fps = QSpinBox()
        self.spn_fps.setRange(10, 60); self.spn_fps.setValue(self.config.fps)
        self.spn_gravity = QDoubleSpinBox()
        self.spn_gravity.setRange(0.5, 20.0); self.spn_gravity.setSingleStep(0.5)
        self.spn_gravity.setValue(getattr(self.config, 'gravity', 9.0))
        self.spn_max = QSpinBox()
        self.spn_max.setRange(1, 50); self.spn_max.setValue(self.config.max_mascots)
        form_phys.addRow("Vitesse marche :",       self.spn_walk)
        form_phys.addRow("FPS :",                   self.spn_fps)
        form_phys.addRow("Gravité :",               self.spn_gravity)
        form_phys.addRow("Nb max personnages :",    self.spn_max)
        tabs.addTab(tab_phys, "🌍 Physique")

        # ── Onglet Debug ───────────────────────────────────────────────────
        tab_dbg = QWidget()
        vd = QVBoxLayout(tab_dbg)
        vd.setContentsMargins(12, 12, 12, 12)
        self.chk_debug = QCheckBox("Afficher overlay debug (état, position, vélocité)")
        self.chk_debug.setChecked(getattr(self.config, 'debug_overlay', False))
        vd.addWidget(self.chk_debug)
        vd.addStretch()
        tabs.addTab(tab_dbg, "🐞 Debug")

        # Boutons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_personality_for(self, char_name: str) -> None:
        self._current_char = char_name
        text = self.config.character_personalities.get(char_name, "")
        self.txt_personality.setPlainText(text)

    def _on_char_changed(self, new_char: str) -> None:
        if hasattr(self, '_current_char') and self._current_char:
            txt = self.txt_personality.toPlainText().strip()
            if txt:
                self.config.character_personalities[self._current_char] = txt
            elif self._current_char in self.config.character_personalities:
                del self.config.character_personalities[self._current_char]
        self._load_personality_for(new_char)

    def _save(self) -> None:
        self.config.ai_backend            = self.cmb_backend.currentText()
        # Ollama
        self.config.ollama_url            = self.txt_ollama_url.text().strip()
        self.config.ollama_model          = self.txt_ollama_model.text().strip()
        # LM Studio
        self.config.lm_studio_url         = self.txt_lms_url.text().strip()
        self.config.lm_studio_model       = self.txt_lms_model.text().strip()
        # OpenRouter
        self.config.openrouter_api_key    = self.txt_or_key.text().strip()
        self.config.openrouter_model      = self.txt_or_model.text().strip()
        # xAI
        self.config.xai_api_key           = self.txt_xai_key.text().strip()
        self.config.xai_model             = self.txt_xai_model.text().strip()
        # Anthropic
        self.config.anthropic_api_key     = self.txt_ant_key.text().strip()
        self.config.anthropic_model       = self.txt_ant_model.text().strip()
        # Gemini
        self.config.gemini_api_key        = self.txt_gem_key.text().strip()
        self.config.gemini_model          = self.txt_gem_model.text().strip()
        # Custom
        self.config.custom_base_url       = self.txt_cus_url.text().strip()
        self.config.custom_api_key        = self.txt_cus_key.text().strip()
        self.config.custom_model          = self.txt_cus_model.text().strip()
        self._on_char_changed("")
        self.config.character_name        = self.cmb_char.currentText()
        self.config.character_personality = self.txt_default_personality.toPlainText().strip()
        self.config.mascot_scale          = self.spn_scale.value()
        self.config.walk_speed            = self.spn_walk.value()
        self.config.fps                   = self.spn_fps.value()
        self.config.gravity               = self.spn_gravity.value()
        self.config.max_mascots           = self.spn_max.value()
        self.config.enable_walk_with_ie   = self.chk_walk_ie.isChecked()
        self.config.enable_throw_ie       = self.chk_throw_ie.isChecked()
        self.config.enable_jump           = self.chk_jump.isChecked()
        self.config.enable_special        = self.chk_special.isChecked()
        self.config.behavior_freq_scale   = self.sld_freq.value() / 100.0
        # Social
        self.config.enable_conversations  = self.chk_conversations.isChecked()
        self.config.enable_bubbles        = self.chk_bubbles.isChecked()
        self.config.enable_mood_indicator = self.chk_mood.isChecked()
        self.config.enable_minigames      = self.chk_minigames.isChecked()
        self.config.enable_sleep          = self.chk_sleep.isChecked()
        self.config.enable_system_reactions = self.chk_system_react.isChecked()
        # Mémoire
        self.config.enable_memory         = self.chk_memory.isChecked()
        self.config.enable_summary        = self.chk_summary.isChecked()
        self.config.memory_max_messages   = self.spn_max_msgs.value()
        self.config.debug_overlay         = self.chk_debug.isChecked()
        self.config.save()
        self.accept()


# ─────────────────────────────────────────────────────────────────────────────
# TrayIcon
# ─────────────────────────────────────────────────────────────────────────────

class TrayIcon(QSystemTrayIcon):
    def __init__(self, controller: "MascotController", app: QApplication):
        super().__init__()
        self.controller = controller
        self.app        = app

        icon_path = _APP_ROOT / "assets" / "tray.png"
        if not icon_path.exists():
            icon_path = _APP_ROOT / "assets" / "default" / "img" / "icon.png"
        self.setIcon(QIcon(str(icon_path)) if icon_path.exists() else _make_tray_icon())
        self.setToolTip("Shimeji Desk — Clic droit pour le menu")

        self._build_menu()
        self.activated.connect(self._on_activated)

    def _build_menu(self) -> None:
        menu = QMenu()
        menu.setStyleSheet(_MENU_STYLE)

        # ── Header avec compteur ──────────────────────────────────────────
        hdr_action = QWidgetAction(menu)
        hdr_widget = _MenuHeader(self.controller)
        hdr_widget.setStyleSheet(f"background: {_C_BG2};")
        hdr_action.setDefaultWidget(hdr_widget)
        menu.addAction(hdr_action)

        # Ligne de séparation stylisée
        menu.addSeparator()

        # ── Personnages ───────────────────────────────────────────────────
        chars_act = menu.addAction("🎭  Choisir les personnages…")
        chars_act.triggered.connect(self._open_character_selector)

        spawn_act = menu.addAction("✦  Ajouter un personnage aléatoire")
        spawn_act.triggered.connect(lambda: self.controller.spawn_random())

        spawn_all_act = menu.addAction("✦✦ Ajouter tous les personnages")
        spawn_all_act.triggered.connect(self._spawn_all)

        import_act = menu.addAction("📦  Importer un pack Shimeji…")
        import_act.triggered.connect(self._import_pack)

        menu.addSeparator()

        # ── Gestion ───────────────────────────────────────────────────────
        dismiss_act = menu.addAction("✖  Retirer tous les personnages")
        dismiss_act.triggered.connect(self._dismiss_all_confirm)

        freeze_act = menu.addAction("❄  Figer / Reprendre les animations")
        freeze_act.triggered.connect(self._toggle_freeze)

        menu.addSeparator()

        # ── Chat IA ───────────────────────────────────────────────────────
        chat_act = menu.addAction("💬  Ouvrir un chat IA…")
        chat_act.triggered.connect(self._open_chat_picker)

        menu.addSeparator()

        # ── Paramètres ────────────────────────────────────────────────────
        settings_act = menu.addAction("⚙  Paramètres")
        settings_act.triggered.connect(self._open_settings)

        theme_act = menu.addAction("🎨  Thème visuel…")
        theme_act.triggered.connect(self._open_theme_picker)

        about_act = menu.addAction("ℹ  À propos")
        about_act.triggered.connect(self._show_about)

        menu.addSeparator()

        quit_act = menu.addAction("⏻  Quitter")
        quit_act.triggered.connect(self.app.quit)

        self.setContextMenu(menu)
        self._frozen = False

    # ── Actions ──────────────────────────────────────────────────────────────

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._open_character_selector()

    def _open_character_selector(self) -> None:
        from ui.character_selector import CharacterSelectorDialog
        chars = self.controller.available_characters()
        if not chars:
            self.showMessage("Shimeji Desk", "Aucun personnage trouvé dans assets/",
                             QSystemTrayIcon.MessageIcon.Warning, 3000)
            return
        dlg = CharacterSelectorDialog(chars)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            selected = dlg.selected_paths()
            if not selected:
                return
            self.controller.dismiss_all()
            for path in selected:
                self.controller.spawn_mascot(str(path))
            self.showMessage("Shimeji Desk",
                             f"{len(selected)} personnage(s) spawnés !",
                             QSystemTrayIcon.MessageIcon.Information, 2000)

    def _spawn_all(self) -> None:
        """Spawner un exemplaire de chaque personnage disponible."""
        chars = self.controller.available_characters()
        if not chars:
            return
        self.controller.dismiss_all()
        count = 0
        for path in chars:
            if self.controller.spawn_mascot(str(path)):
                count += 1
        self.showMessage("Shimeji Desk",
                         f"{count} personnages invoqués !",
                         QSystemTrayIcon.MessageIcon.Information, 2000)

    def _dismiss_all_confirm(self) -> None:
        """Retirer tous les personnages avec confirmation via message tray."""
        n = len(self.controller.mascots)
        if n == 0:
            self.showMessage("Shimeji Desk", "Aucun personnage actif.",
                             QSystemTrayIcon.MessageIcon.Information, 1500)
            return
        self.controller.dismiss_all()
        self.showMessage("Shimeji Desk", f"{n} personnage(s) retiré(s).",
                         QSystemTrayIcon.MessageIcon.Information, 2000)

    def _toggle_freeze(self) -> None:
        """Figer ou reprendre les animations de tous les persos."""
        self._frozen = not self._frozen
        try:
            timer = self.controller._mascot_timer
            if self._frozen:
                timer.stop()
            else:
                timer.start()
        except Exception:
            pass
        state = "figés ❄" if self._frozen else "repris ▶"
        self.showMessage("Shimeji Desk", f"Personnages {state}.",
                         QSystemTrayIcon.MessageIcon.Information, 1500)

    def _open_chat_picker(self) -> None:
        """Choisir avec quel personnage ouvrir un chat IA."""
        if not self.controller.mascots:
            self.showMessage("Shimeji Desk",
                             "Aucun personnage actif. Spawn un personnage d'abord !",
                             QSystemTrayIcon.MessageIcon.Warning, 2500)
            return
        # Si un seul perso, ouvrir directement
        if len(self.controller.mascots) == 1:
            self.controller.mascots[0].chat_requested.emit(
                self.controller.mascots[0])
            return
        # Plusieurs persos → menu contextuel pour choisir
        pick = QMenu()
        pick.setStyleSheet(_MENU_STYLE)
        pick.addAction("Choisir un personnage :").setEnabled(False)
        pick.addSeparator()
        for m in self.controller.mascots:
            name = getattr(m, 'character_name', '?')
            mid  = getattr(m, 'mascot_id', '?')
            act  = pick.addAction(f"  {name} #{mid}")
            act.triggered.connect(lambda checked, mascot=m:
                                  mascot.chat_requested.emit(mascot))
        pick.exec(self.geometry().topLeft())

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self.controller.config)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.controller.reload_ai()
            self.showMessage("Shimeji Desk", "Paramètres sauvegardés ✓",
                             QSystemTrayIcon.MessageIcon.Information, 2000)

    def _open_theme_picker(self) -> None:
        """Sélectionner un thème visuel pour les menus et bulles."""
        THEMES = {
            "◈ Arknights (défaut)": {
                "bg": "#0d0d1a", "bg2": "#131326", "border": "#2a2a6a",
                "accent": "#4a9eff", "text": "#c8d8ff",
            },
            "🌿 Nature": {
                "bg": "#0d1a0f", "bg2": "#122018", "border": "#1e4a2a",
                "accent": "#3dff9a", "text": "#c8ffd4",
            },
            "🔥 Inferno": {
                "bg": "#1a0d0d", "bg2": "#261313", "border": "#6a2a2a",
                "accent": "#ff6a3d", "text": "#ffd4c8",
            },
            "💜 Violet": {
                "bg": "#110d1a", "bg2": "#1a1326", "border": "#4a2a6a",
                "accent": "#c47fff", "text": "#e8d4ff",
            },
            "⬜ Clair": {
                "bg": "#f0f0f8", "bg2": "#e0e0f0", "border": "#a0a0d0",
                "accent": "#2244cc", "text": "#111122",
            },
        }

        pick = QMenu()
        pick.setStyleSheet(_MENU_STYLE)
        pick.addAction("Choisir un thème :").setEnabled(False)
        pick.addSeparator()
        for name in THEMES:
            act = pick.addAction(name)
            act.triggered.connect(
                lambda checked, t=THEMES[name], n=name: self._apply_theme(t, n)
            )
        pick.exec(self.geometry().topLeft())

    def _apply_theme(self, theme: dict, name: str) -> None:
        """Applique un thème aux bulles et menus."""
        try:
            import ui.mascot_bubble as _mb
            _mb.MascotBubble._BG     = QColor(theme["bg"])
            _mb.MascotBubble._BORDER = QColor(theme["accent"])
            _mb.MascotBubble._TEXT   = QColor(theme["text"])
            _mb.MascotBubble._NAME   = QColor(theme["accent"])
        except Exception:
            pass
        self.showMessage("Shimeji Desk", f"Thème appliqué : {name}",
                         QSystemTrayIcon.MessageIcon.Information, 2000)

    def _import_pack(self) -> None:
        """Importer un pack Shimeji (ZIP ou dossier)."""
        from PyQt6.QtWidgets import QFileDialog
        from core.pack_importer import import_pack, scan_available_chars

        # Sélectionner un fichier ZIP ou un dossier
        path, _ = QFileDialog.getOpenFileName(
            None, "Importer un pack Shimeji",
            "", "Packs Shimeji (*.zip);;Tous les fichiers (*)"
        )
        if not path:
            # Essayer la sélection de dossier
            path = QFileDialog.getExistingDirectory(
                None, "Ou sélectionner un dossier de personnage", ""
            )
        if not path:
            return

        ok, msg = import_pack(path)
        icon = QSystemTrayIcon.MessageIcon.Information if ok else QSystemTrayIcon.MessageIcon.Warning
        self.showMessage("Shimeji Desk — Import", msg, icon, 5000)

        if ok:
            # Rescanner les personnages disponibles
            new_chars = scan_available_chars()
            self.controller._available_chars = new_chars
            print(f"[Import] {len(new_chars)} personnages disponibles après import")
        dlg = SettingsDialog(self.controller.config)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.controller.reload_ai()
            self.showMessage("Shimeji Desk", "Paramètres sauvegardés ✓",
                             QSystemTrayIcon.MessageIcon.Information, 2000)

    def _show_about(self) -> None:
        from PyQt6.QtWidgets import QMessageBox
        mb = QMessageBox()
        mb.setWindowTitle("À propos — Shimeji Desk")
        mb.setStyleSheet(_SETTINGS_STYLE)
        mb.setText(
            "<b style='color:#4a9eff; font-family:Consolas'>◈ SHIMEJI DESK</b><br><br>"
            "Clone Python/PyQt6 de Shimeji-ee<br>"
            "avec intégration IA (Ollama / OpenRouter)<br><br>"
            "<span style='color:#6878aa'>Sprites : Arknights Shimeji Pack v1.1</span><br>"
            "<span style='color:#6878aa'>Développé avec Claude (Anthropic)</span>"
        )
        mb.setIcon(QMessageBox.Icon.NoIcon)
        mb.exec()
