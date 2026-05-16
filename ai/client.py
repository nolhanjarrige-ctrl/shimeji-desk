"""ai/client.py – Client IA multi-backend.

Backends supportés :
  openai_compat  → Ollama, LM Studio, OpenRouter, xAI/Grok, Custom
  anthropic      → Claude (api.anthropic.com)
  gemini         → Google Gemini (generativelanguage.googleapis.com)

Chaque backend est décrit par (base_url, api_key, model, wire_format).
"""
from __future__ import annotations
import asyncio
import json
from typing import AsyncIterator

import httpx

from ai.memory import MemoryManager
from config import Config

SYSTEM_TEMPLATE = """{personality}

Ton nom est {name}. Tu es visible sur l'écran de l'utilisateur sous forme de personnage animé.
Tu peux aider avec des tâches variées (code, rédaction, questions, etc.) tout en restant sympathique.

{memory_context}
"""

# ── Constantes backends ────────────────────────────────────────────────────
_BACKENDS: dict[str, dict] = {
    "ollama":     {"fmt": "ollama",   "url": ""},          # url depuis config
    "lm_studio":  {"fmt": "openai",   "url": ""},          # url depuis config
    "openrouter": {"fmt": "openai",   "url": "https://openrouter.ai/api/v1"},
    "xai":        {"fmt": "openai",   "url": "https://api.x.ai/v1"},
    "anthropic":  {"fmt": "anthropic","url": "https://api.anthropic.com/v1/messages"},
    "gemini":     {"fmt": "gemini",   "url": "https://generativelanguage.googleapis.com/v1beta"},
    "custom":     {"fmt": "openai",   "url": ""},          # url depuis config
}


class AIClient:

    def __init__(self, config: Config, memory: MemoryManager):
        self.config = config
        self.memory = memory
        self._http  = httpx.AsyncClient(timeout=120.0)

    # ── Résolution backend ─────────────────────────────────────────────────

    @property
    def _backend(self) -> str:
        return self.config.ai_backend

    @property
    def _fmt(self) -> str:
        return _BACKENDS.get(self._backend, {}).get("fmt", "openai")

    @property
    def _model(self) -> str:
        b = self._backend
        if b == "ollama":      return self.config.ollama_model
        if b == "lm_studio":   return self.config.lm_studio_model
        if b == "openrouter":  return self.config.openrouter_model
        if b == "xai":         return self.config.xai_model
        if b == "anthropic":   return self.config.anthropic_model
        if b == "gemini":      return self.config.gemini_model
        if b == "custom":      return self.config.custom_model
        return "gpt-4o-mini"

    @property
    def _api_key(self) -> str:
        b = self._backend
        if b == "openrouter": return self.config.openrouter_api_key
        if b == "xai":        return self.config.xai_api_key
        if b == "anthropic":  return self.config.anthropic_api_key
        if b == "gemini":     return self.config.gemini_api_key
        if b == "custom":     return self.config.custom_api_key
        return ""

    @property
    def _base_url(self) -> str:
        b = self._backend
        if b == "ollama":    return self.config.ollama_url.rstrip("/")
        if b == "lm_studio": return self.config.lm_studio_url.rstrip("/")
        if b == "custom":    return self.config.custom_base_url.rstrip("/")
        return _BACKENDS[b]["url"]

    @property
    def _chat_url(self) -> str:
        if self._fmt == "ollama":    return f"{self._base_url}/api/chat"
        if self._fmt == "gemini":
            return (f"{self._base_url}/models/{self._model}"
                    f":generateContent?key={self._api_key}")
        if self._fmt == "anthropic": return self._base_url
        return f"{self._base_url}/chat/completions"

    @property
    def _stream_url(self) -> str:
        if self._fmt == "gemini":
            return (f"{self._base_url}/models/{self._model}"
                    f":streamGenerateContent?key={self._api_key}&alt=sse")
        return self._chat_url

    @property
    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        fmt = self._fmt
        if fmt == "openai" and self._api_key:
            h["Authorization"] = f"Bearer {self._api_key}"
            if self._backend == "openrouter":
                h["HTTP-Referer"] = "https://github.com/shimeji-desk"
                h["X-Title"]      = "Shimeji Desk"
        elif fmt == "anthropic":
            h["x-api-key"]         = self._api_key
            h["anthropic-version"] = "2023-06-01"
        # gemini: clé dans l'URL, pas de header
        return h

    # ── Prompt ────────────────────────────────────────────────────────────

    def _build_system_prompt(self, character_name: str) -> str:
        context_msgs = self.memory.get_context_messages(character_name)
        memory_parts = [m["content"] for m in context_msgs if m["role"] == "system"]
        memory_context = "\n".join(memory_parts) if memory_parts else ""
        return SYSTEM_TEMPLATE.format(
            personality=self.config.get_personality(character_name),
            name=character_name,
            memory_context=memory_context,
        )

    def _build_messages(self, user_message: str, character_name: str) -> list[dict]:
        history = self.memory.get_recent_messages(character_name, n=20)
        return [
            {"role": "system", "content": self._build_system_prompt(character_name)},
            *history,
            {"role": "user", "content": user_message},
        ]

    # ── Payload builders ──────────────────────────────────────────────────

    def _payload(self, messages: list[dict], stream: bool) -> dict:
        fmt = self._fmt
        if fmt in ("openai", "ollama"):
            return {"model": self._model, "messages": messages, "stream": stream}

        if fmt == "anthropic":
            # Séparer system et conversation
            sys_txt  = next((m["content"] for m in messages if m["role"] == "system"), "")
            convo    = [m for m in messages if m["role"] != "system"]
            p = {"model": self._model, "max_tokens": 2048,
                 "messages": convo, "stream": stream}
            if sys_txt:
                p["system"] = sys_txt
            return p

        if fmt == "gemini":
            sys_txt = next((m["content"] for m in messages if m["role"] == "system"), "")
            convo   = []
            for m in messages:
                if m["role"] == "system":
                    continue
                role = "model" if m["role"] == "assistant" else "user"
                convo.append({"role": role, "parts": [{"text": m["content"]}]})
            p: dict = {"contents": convo}
            if sys_txt:
                p["systemInstruction"] = {"parts": [{"text": sys_txt}]}
            return p

        raise ValueError(f"[AIClient] Format inconnu : {self._fmt}")

    # ── Extraction réponse ────────────────────────────────────────────────

    def _extract_reply(self, data: dict) -> str:
        fmt = self._fmt
        # Ollama natif
        if fmt == "ollama" and "message" in data:
            return data["message"].get("content", "")
        # OpenAI-compatible
        if "choices" in data and data["choices"]:
            return data["choices"][0]["message"].get("content", "")
        # Anthropic
        if "content" in data and isinstance(data["content"], list):
            return "".join(b.get("text","") for b in data["content"]
                           if b.get("type") == "text")
        # Gemini
        if "candidates" in data and data["candidates"]:
            parts = data["candidates"][0].get("content", {}).get("parts", [])
            return "".join(p.get("text","") for p in parts)
        return f"[Format inattendu — clés : {list(data.keys())}]"

    def _extract_stream_token(self, line: str) -> str:
        """Extrait un token d'une ligne SSE selon le format du backend."""
        fmt = self._fmt
        try:
            if fmt == "ollama":
                obj = json.loads(line)
                if obj.get("done"):
                    return "\x00"  # signal fin
                return obj.get("message", {}).get("content", "")

            # SSE standard (OpenAI, xAI, OpenRouter, Anthropic, Gemini)
            if not line.startswith("data: "):
                # Anthropic envoie aussi des lignes "event: ..."
                if fmt == "anthropic" and line.startswith("{"):
                    obj = json.loads(line)
                    return obj.get("delta", {}).get("text", "")
                return ""
            raw = line[6:].strip()
            if raw == "[DONE]":
                return "\x00"

            obj = json.loads(raw)
            if fmt in ("openai", "ollama"):
                return obj["choices"][0]["delta"].get("content", "")
            if fmt == "anthropic":
                if obj.get("type") == "content_block_delta":
                    return obj.get("delta", {}).get("text", "")
                if obj.get("type") == "message_stop":
                    return "\x00"
            if fmt == "gemini":
                cands = obj.get("candidates", [])
                if cands:
                    parts = cands[0].get("content", {}).get("parts", [])
                    return "".join(p.get("text","") for p in parts)
        except (json.JSONDecodeError, KeyError, IndexError):
            pass
        return ""

    # ── Chat non-streamé ──────────────────────────────────────────────────

    async def chat(self, user_message: str, character_name: str) -> str:
        messages = self._build_messages(user_message, character_name)
        payload  = self._payload(messages, stream=False)
        is_error = False
        try:
            resp = await self._http.post(
                self._chat_url, headers=self._headers, json=payload)
            resp.raise_for_status()
            reply = self._extract_reply(resp.json())
        except Exception as e:
            reply    = f"[Erreur IA : {e}]"
            is_error = True

        if not is_error and getattr(self.config, 'enable_memory', True):
            self.memory.add_message(character_name, "user",      user_message)
            self.memory.add_message(character_name, "assistant", reply)
            self._maybe_summarize(character_name)
        return reply

    # ── Chat streamé ──────────────────────────────────────────────────────

    async def stream_chat(
        self, user_message: str, character_name: str
    ) -> AsyncIterator[str]:
        messages   = self._build_messages(user_message, character_name)
        payload    = self._payload(messages, stream=True)
        full_reply = ""
        try:
            async with self._http.stream(
                "POST", self._stream_url, headers=self._headers, json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    token = self._extract_stream_token(line)
                    if token == "\x00":
                        break
                    if token:
                        full_reply += token
                        yield token
        except Exception as e:
            yield f"[Erreur IA : {e}]"
            full_reply = ""

        if full_reply and getattr(self.config, 'enable_memory', True):
            self.memory.add_message(character_name, "user",      user_message)
            self.memory.add_message(character_name, "assistant", full_reply)
            self._maybe_summarize(character_name)

    # ── Résumé automatique ────────────────────────────────────────────────

    def _maybe_summarize(self, character_name: str) -> None:
        if not getattr(self.config, "enable_summary", True):
            return
        if (character_name == "__summary__"
                or character_name.startswith("__conv_")
                or character_name == "__autopersonality__"):
            return
        count = self.memory.message_count(character_name)
        if count > 0 and count % 40 == 0:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    task = asyncio.ensure_future(self._auto_summarize(character_name))
                    task.add_done_callback(lambda _t: None)
            except RuntimeError:
                pass

    async def _auto_summarize(self, character_name: str) -> None:
        history = self.memory.get_recent_messages(character_name, n=30)
        if not history:
            return
        convo  = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in history)
        prompt = (f"Résume en 3-5 phrases les échanges importants entre "
                  f"l'utilisateur et {character_name} :\n\n{convo}")
        try:
            reply = await self.chat(prompt, "__summary__")
            if reply and not reply.startswith("[Erreur"):
                self.memory.save_summary(character_name, reply)
        except Exception as e:
            print(f"[AI] Erreur résumé : {e}")

    # ── Test connexion ────────────────────────────────────────────────────

    async def test_connection(self) -> tuple[bool, str]:
        try:
            fmt = self._fmt
            if fmt == "ollama":
                url  = f"{self._base_url}/api/tags"
                resp = await self._http.get(url, timeout=5.0)
                if resp.status_code == 200:
                    models = [m["name"] for m in resp.json().get("models", [])]
                    return True, f"Ollama ✓ — {len(models)} modèle(s)"
            elif fmt == "gemini":
                url  = (f"{self._base_url}/models?key={self._api_key}")
                resp = await self._http.get(url, timeout=5.0)
                if resp.status_code == 200:
                    return True, "Gemini ✓"
            elif fmt == "anthropic":
                # Anthropic n'a pas d'endpoint /models public simple, on teste /messages
                return True, "Anthropic — clé configurée (non testable sans requête)"
            else:
                # OpenAI-compatible : GET /models
                url  = f"{self._base_url}/models"
                h    = self._headers.copy()
                resp = await self._http.get(url, headers=h, timeout=5.0)
                if resp.status_code == 200:
                    data   = resp.json()
                    models = [m.get("id","?") for m in data.get("data", [])[:3]]
                    return True, f"{self._backend} ✓ — ex: {', '.join(models)}"
            return False, f"HTTP {resp.status_code}"
        except Exception as e:
            return False, str(e)

    async def close(self) -> None:
        await self._http.aclose()
