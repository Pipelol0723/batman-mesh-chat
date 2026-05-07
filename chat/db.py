"""
db.py — Historial persistente con SQLite

Tabla `messages`:
  id          INTEGER PRIMARY KEY
  timestamp   TEXT    ISO-8601
  sender      TEXT    nombre del usuario
  msg_type    TEXT    'text' | 'file' | 'photo' | 'system'
  content     TEXT    cuerpo del mensaje o ruta local del archivo
  filename    TEXT    nombre original del archivo (nullable)
  peer_ip     TEXT    IP del peer origen (nullable)
"""

import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

DB_PATH = Path.home() / ".batman-chat" / "history.db"


class Database:
    """Base de datos thread-safe para el historial de mensajes."""

    def __init__(self, db_path: Path = DB_PATH):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            str(db_path), check_same_thread=False, isolation_level=None
        )
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    # ── Schema ─────────────────────────────────────────────────────────────

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT    NOT NULL,
                sender    TEXT    NOT NULL,
                msg_type  TEXT    NOT NULL DEFAULT 'text',
                content   TEXT    NOT NULL DEFAULT '',
                filename  TEXT,
                peer_ip   TEXT
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_timestamp ON messages(timestamp)"
        )

    # ── Escritura ──────────────────────────────────────────────────────────

    def save_message(
        self,
        sender: str,
        msg_type: str,
        content: str,
        filename: Optional[str] = None,
        peer_ip: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> None:
        ts = timestamp or datetime.now().isoformat(timespec="seconds")
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO messages (timestamp, sender, msg_type, content, filename, peer_ip)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (ts, sender, msg_type, content, filename, peer_ip),
            )

    # ── Lectura ────────────────────────────────────────────────────────────

    def get_history(self, limit: int = 100) -> List[Dict]:
        """Retorna los últimos `limit` mensajes, del más antiguo al más nuevo."""
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT timestamp, sender, msg_type, content, filename
                FROM messages
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cur.fetchall()

        rows.reverse()
        return [
            {
                "timestamp": r[0],
                "sender": r[1],
                "type": r[2],
                "content": r[3],
                "filename": r[4],
            }
            for r in rows
        ]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
