"""config.py – Configuration globale de Shimeji Desk"""
from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class Config:
    # ── Personnage ────────────────────────────────────────────────────
    character_path: str = "assets/default"
    character_name: str = "Shimeji"
    character_personality: str = (
        "Tu es un petit personnage de bureau espiègle et attachant. "
        "Tu te déplaces sur l'écran et tu aides ton utilisateur avec enthousiasme. "
        "Tu réponds en français, de façon concise et chaleureuse."
    )
    # Personnalités individuelles : {nom_perso: texte}  (fallback → character_personality)
    character_personalities: dict = field(default_factory=dict)
    language: str = "fr"

    # ── IA ────────────────────────────────────────────────────────────
    ai_backend: str = "ollama"   # ollama|lm_studio|openrouter|xai|anthropic|gemini|custom

    # Ollama (local)
    ollama_url:   str = "http://localhost:11434"
    ollama_model: str = "llama3"

    # LM Studio (local OpenAI-compatible)
    lm_studio_url:   str = "http://localhost:1234/v1"
    lm_studio_model: str = "local-model"

    # OpenRouter (cloud, accès 200+ modèles)
    openrouter_api_key: str = ""
    openrouter_model:   str = "openai/gpt-4o-mini"

    # xAI / Grok (cloud, OpenAI-compatible)
    xai_api_key: str = ""
    xai_model:   str = "grok-3-mini"

    # Anthropic / Claude (cloud)
    anthropic_api_key: str = ""
    anthropic_model:   str = "claude-sonnet-4-5"

    # Google Gemini (cloud)
    gemini_api_key: str = ""
    gemini_model:   str = "gemini-2.0-flash"

    # Custom (tout endpoint OpenAI-compatible)
    custom_base_url: str = "http://localhost:8080/v1"
    custom_api_key:  str = ""
    custom_model:    str = "model-name"


    # ── Physique ──────────────────────────────────────────────────────
    mascot_scale: float = 1.0
    gravity: float = 9.0
    walk_speed: float = 2.0
    fps: int = 30
    window_refresh_ms: int = 200
    max_mascots: int = 30

    # ── Comportements ─────────────────────────────────────────────────
    enable_walk_with_ie:  bool  = True
    enable_throw_ie:      bool  = True
    enable_jump:          bool  = True
    enable_special:       bool  = True

    # ── Interactions & Social ──────────────────────────────────────────────
    enable_conversations:    bool = True   # conversations inter-persos
    enable_mood_indicator:   bool = True   # icônes d'humeur
    enable_bubbles:          bool = True   # bulles de dialogue
    enable_minigames:        bool = True   # mini-jeux PFC
    enable_sleep:            bool = True   # cycle sommeil/réveil 22h–6h
    enable_system_reactions: bool = True   # réactions horaires et jours spéciaux

    # ── Mémoire & IA ──────────────────────────────────────────────────────
    enable_memory:        bool  = True   # sauvegarder l'historique des chats
    enable_summary:       bool  = True   # résumés automatiques (toutes les 40 msgs)
    memory_max_messages:  int   = 50     # messages max par perso en base
    behavior_freq_scale:  float = 1.0

    # ── Debug ─────────────────────────────────────────────────────────
    debug_overlay: bool = False

    # ── API personnalités ─────────────────────────────────────────────

    def get_personality(self, char_name: str) -> str:
        return self.character_personalities.get(char_name, self.character_personality)

    def set_personality(self, char_name: str, text: str) -> None:
        if text.strip():
            self.character_personalities[char_name] = text.strip()
        elif char_name in self.character_personalities:
            del self.character_personalities[char_name]

    # ── Persistance ───────────────────────────────────────────────────

    @classmethod
    def load(cls, path: str = "config.json") -> "Config":
        p = Path(path)
        if not p.exists():
            cfg = cls()
            cfg.save(path)
            return cfg
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        known = cls.__dataclass_fields__
        filtered = {k: v for k, v in data.items() if k in known}
        if "character_personalities" in filtered and \
                not isinstance(filtered["character_personalities"], dict):
            filtered["character_personalities"] = {}
        return cls(**filtered)

    def save(self, path: str = "config.json") -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)
