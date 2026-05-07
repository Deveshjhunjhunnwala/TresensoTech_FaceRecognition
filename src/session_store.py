from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
import os
import sqlite3
import uuid


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SESSION_DB_FILE = Path(os.getenv("ATTENDANCE_SESSION_DB_FILE", str(DATA_DIR / "session_store.db")))
SESSION_TTL_SECONDS = int(os.getenv("ATTENDANCE_SESSION_TTL_SECONDS", "300"))


@dataclass(frozen=True)
class SessionState:
    session_id: str
    username: str
    expires_at: datetime


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat(timespec="seconds")


@contextmanager
def get_connection() -> sqlite3.Connection:
    SESSION_DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(SESSION_DB_FILE, timeout=30)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


class SQLiteSessionStore:
    def __init__(self, db_file: Path, ttl_seconds: int) -> None:
        self.db_file = db_file
        self.ttl_seconds = ttl_seconds
        self._initialize_database()

    def _initialize_database(self) -> None:
        with get_connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS auth_sessions (
                    session_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_auth_sessions_expires_at
                ON auth_sessions(expires_at)
                """
            )

    def _purge_expired_sessions(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            "DELETE FROM auth_sessions WHERE expires_at <= ?",
            (_utc_now_iso(),),
        )

    def ping(self) -> None:
        self._initialize_database()
        with get_connection() as connection:
            self._purge_expired_sessions(connection)
            connection.execute("SELECT 1").fetchone()

    def create_session(self, username: str) -> SessionState:
        session_id = str(uuid.uuid4())
        created_at = _utc_now()
        expires_at = created_at + timedelta(seconds=self.ttl_seconds)
        with get_connection() as connection:
            self._purge_expired_sessions(connection)
            connection.execute(
                """
                INSERT INTO auth_sessions (session_id, username, created_at, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    session_id,
                    username,
                    created_at.isoformat(timespec="seconds"),
                    expires_at.isoformat(timespec="seconds"),
                ),
            )
        return SessionState(session_id=session_id, username=username, expires_at=expires_at)

    def get_session(self, session_id: str) -> SessionState | None:
        with get_connection() as connection:
            self._purge_expired_sessions(connection)
            row = connection.execute(
                """
                SELECT session_id, username, expires_at
                FROM auth_sessions
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
            if row is None:
                return None
            expires_at = datetime.fromisoformat(row["expires_at"])
            if expires_at <= _utc_now():
                connection.execute("DELETE FROM auth_sessions WHERE session_id = ?", (session_id,))
                return None
            return SessionState(
                session_id=row["session_id"],
                username=row["username"],
                expires_at=expires_at,
            )

    def delete_session(self, session_id: str) -> None:
        with get_connection() as connection:
            connection.execute("DELETE FROM auth_sessions WHERE session_id = ?", (session_id,))

    def clear_all_sessions(self) -> None:
        with get_connection() as connection:
            connection.execute("DELETE FROM auth_sessions")


@lru_cache(maxsize=1)
def get_session_store() -> SQLiteSessionStore:
    return SQLiteSessionStore(db_file=SESSION_DB_FILE, ttl_seconds=SESSION_TTL_SECONDS)
