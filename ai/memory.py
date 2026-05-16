"""ai/memory.py – Mémoire conversationnelle SQLite pour le personnage IA."""
from __future__ import annotations
import sqlite3
import json
from pathlib import Path
from typing import Optional


DB_PATH = Path("shimeji_memory.db")


class MemoryManager:
    """
    Stocke et retrouve les conversations par personnage.
    Tronque automatiquement l'historique et génère des résumés.
    """

    def __init__(self, db_path: Optional[str] = None, max_messages: int = 50):
        self.db_path = Path(db_path) if db_path else DB_PATH
        self.max_messages = max_messages
        self._db: sqlite3.Connection = sqlite3.connect(
            str(self.db_path), check_same_thread=False
        )
        self._db.execute("PRAGMA journal_mode=WAL")
        self._init_db()
        # Nettoyer les résidus de conversations inter-persos et résumés temporaires
        # Ces entrées __conv_X__ et __summary__ ne doivent pas persister entre sessions
        try:
            self._db.execute(
                "DELETE FROM messages WHERE character LIKE '__conv_%' "
                "OR character = '__summary__'"
            )
            self._db.execute(
                "DELETE FROM summaries WHERE character LIKE '__conv_%' "
                "OR character = '__summary__'"
            )
            self._db.commit()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Init DB
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS messages (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    character   TEXT NOT NULL,
                    role        TEXT NOT NULL,
                    content     TEXT NOT NULL,
                    created_at  TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS summaries (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    character   TEXT NOT NULL,
                    summary     TEXT NOT NULL,
                    created_at  TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS relations (
                    char_a      TEXT NOT NULL,
                    char_b      TEXT NOT NULL,
                    score       REAL DEFAULT 0.0,
                    meetings    INTEGER DEFAULT 0,
                    last_topic  TEXT DEFAULT '',
                    updated_at  TEXT DEFAULT (datetime('now')),
                    PRIMARY KEY (char_a, char_b)
                );

                CREATE INDEX IF NOT EXISTS idx_messages_char ON messages(character);
                CREATE INDEX IF NOT EXISTS idx_summaries_char ON summaries(character);
            """)

    # ── Relations entre persos ────────────────────────────────────────────

    def _rel_key(self, a: str, b: str) -> tuple[str, str]:
        """Clé canonique (ordre alphabétique) pour la relation."""
        return (a, b) if a < b else (b, a)

    def get_relation(self, char_a: str, char_b: str) -> dict:
        """Retourne la relation entre deux persos (score, meetings, last_topic)."""
        ka, kb = self._rel_key(char_a, char_b)
        with self._conn() as conn:
            row = conn.execute(
                "SELECT score, meetings, last_topic FROM relations "
                "WHERE char_a=? AND char_b=?", (ka, kb)
            ).fetchone()
        if row:
            return {"score": row[0], "meetings": row[1], "last_topic": row[2]}
        return {"score": 0.0, "meetings": 0, "last_topic": ""}

    def get_all_relations(self, char: str) -> list[dict]:
        """Retourne toutes les relations impliquant ce personnage."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT char_a, char_b, score, meetings, last_topic "
                "FROM relations WHERE char_a=? OR char_b=? "
                "ORDER BY ABS(score) DESC",
                (char, char)
            ).fetchall()
        return [{"char_a": r[0], "char_b": r[1], "score": r[2],
                 "meetings": r[3], "last_topic": r[4]} for r in rows]

    def update_relation(self, char_a: str, char_b: str,
                        score_delta: float, topic: str = "") -> None:
        """Met à jour la relation entre deux persos après une conversation."""
        ka, kb = self._rel_key(char_a, char_b)
        rel = self.get_relation(ka, kb)
        new_score = max(-100.0, min(100.0, rel["score"] + score_delta))
        new_meet  = rel["meetings"] + 1
        new_topic = topic if topic else rel["last_topic"]
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO relations (char_a, char_b, score, meetings, last_topic, updated_at)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(char_a, char_b) DO UPDATE SET
                    score      = excluded.score,
                    meetings   = excluded.meetings,
                    last_topic = excluded.last_topic,
                    updated_at = excluded.updated_at
            """, (ka, kb, new_score, new_meet, new_topic))

    def relation_label(self, score: float, meetings: int) -> str:
        """Retourne un label lisible pour la relation."""
        if meetings == 0:
            return "inconnus"
        if meetings < 3:
            return "nouvelles connaissances"
        if score >= 60:
            return "meilleurs amis"
        if score >= 30:
            return "amis"
        if score >= 10:
            return "sympathiques"
        if score >= -10:
            return "neutres"
        if score >= -30:
            return "en froid"
        if score >= -60:
            return "rivaux"
        return "ennemis jurés"

    def _conn(self) -> sqlite3.Connection:
        return self._db

    def close(self) -> None:
        try:
            self._db.close()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Écriture
    # ------------------------------------------------------------------

    def add_message(self, character: str, role: str, content: str) -> None:
        """Ajoute un message et tronque si nécessaire."""
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO messages (character, role, content) VALUES (?, ?, ?)",
                (character, role, content),
            )
        self._maybe_truncate(character)

    def save_summary(self, character: str, summary: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO summaries (character, summary) VALUES (?, ?)",
                (character, summary),
            )

    # ------------------------------------------------------------------
    # Lecture
    # ------------------------------------------------------------------

    def get_recent_messages(self, character: str, n: int = 20) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT role, content FROM messages
                   WHERE character = ?
                   ORDER BY id DESC LIMIT ?""",
                (character, n),
            ).fetchall()
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

    def get_latest_summary(self, character: str) -> Optional[str]:
        with self._conn() as conn:
            row = conn.execute(
                """SELECT summary FROM summaries
                   WHERE character = ?
                   ORDER BY id DESC LIMIT 1""",
                (character,),
            ).fetchone()
        return row[0] if row else None

    def get_context_messages(self, character: str) -> list[dict]:
        """
        Construit le contexte complet pour l'API :
        résumé (si disponible) + N messages récents.
        """
        messages = []
        summary = self.get_latest_summary(character)
        if summary:
            messages.append({
                "role": "system",
                "content": f"[Résumé de nos échanges précédents]\n{summary}",
            })
        messages.extend(self.get_recent_messages(character, n=self.max_messages // 2))
        return messages

    def message_count(self, character: str) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE character = ?",
                (character,),
            ).fetchone()
        return row[0] if row else 0

    # ------------------------------------------------------------------
    # Gestion taille
    # ------------------------------------------------------------------

    def _maybe_truncate(self, character: str) -> None:
        """Si trop de messages, supprime les plus anciens."""
        count = self.message_count(character)
        if count > self.max_messages:
            excess = count - self.max_messages
            with self._conn() as conn:
                conn.execute(
                    """DELETE FROM messages WHERE id IN (
                        SELECT id FROM messages WHERE character = ?
                        ORDER BY id ASC LIMIT ?
                    )""",
                    (character, excess),
                )

    def clear(self, character: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM messages WHERE character = ?", (character,))
            conn.execute("DELETE FROM summaries WHERE character = ?", (character,))

    def export_json(self, character: str) -> str:
        return json.dumps({
            "character": character,
            "summary": self.get_latest_summary(character),
            "messages": self.get_recent_messages(character, n=9999),
        }, ensure_ascii=False, indent=2)
