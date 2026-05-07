from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hmac
import os
import re
import sqlite3

import bcrypt

from src.db import init_database
from src.session_store import get_connection, get_session_store


USERNAME_ENV_KEYS = ("ADMIN_USERNAME", "ATTENDANCE_ADMIN_USERNAME")
PASSWORD_HASH_ENV_KEYS = ("ADMIN_PASSWORD_HASH", "ATTENDANCE_ADMIN_PASSWORD_HASH")
MIN_PASSWORD_LENGTH = 10
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._@-]{3,64}$")


@dataclass(frozen=True)
class AuthStatus:
    configured: bool
    setup_required: bool
    source: str


def _first_env(keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = os.getenv(key)
        if value:
            return value
    return None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _initialize_auth_store() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_credentials (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                username TEXT NOT NULL,
                password_hash BLOB NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )


def _fetch_local_credentials() -> sqlite3.Row | None:
    _initialize_auth_store()
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT id, username, password_hash, created_at, updated_at
            FROM admin_credentials
            WHERE id = 1
            """
        ).fetchone()


def _env_admin_username() -> str | None:
    return _first_env(USERNAME_ENV_KEYS)


def _env_admin_password_hash() -> bytes | None:
    value = _first_env(PASSWORD_HASH_ENV_KEYS)
    return value.encode("utf-8") if value else None


def _is_valid_bcrypt_hash(password_hash: bytes | None) -> bool:
    return bool(password_hash and password_hash.startswith((b"$2a$", b"$2b$", b"$2y$")))


def _normalize_username(username: str) -> str:
    normalized = username.strip()
    if not normalized:
        raise ValueError("Username cannot be empty.")
    if not USERNAME_PATTERN.fullmatch(normalized):
        raise ValueError(
            "Username must be 3 to 64 characters and use only letters, numbers, dots, underscores, hyphens, or @."
        )
    return normalized


def _validate_password(password: str) -> None:
    errors: list[str] = []
    if len(password) < MIN_PASSWORD_LENGTH:
        errors.append(f"be at least {MIN_PASSWORD_LENGTH} characters long")
    if not any(character.islower() for character in password):
        errors.append("include a lowercase letter")
    if not any(character.isupper() for character in password):
        errors.append("include an uppercase letter")
    if not any(character.isdigit() for character in password):
        errors.append("include a number")
    if not any(not character.isalnum() for character in password):
        errors.append("include a symbol")
    if errors:
        raise ValueError("Password must " + ", ".join(errors) + ".")


def _write_local_credentials(username: str, password: str) -> None:
    normalized_username = _normalize_username(username)
    _validate_password(password)
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    now = _utc_now_iso()
    _initialize_auth_store()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO admin_credentials (id, username, password_hash, created_at, updated_at)
            VALUES (1, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                username = excluded.username,
                password_hash = excluded.password_hash,
                updated_at = excluded.updated_at
            """,
            (normalized_username, password_hash, now, now),
        )


def get_admin_username() -> str | None:
    local_credentials = _fetch_local_credentials()
    if local_credentials is not None:
        return str(local_credentials["username"])
    return _env_admin_username()


def get_admin_password_hash() -> bytes | None:
    local_credentials = _fetch_local_credentials()
    if local_credentials is not None:
        return bytes(local_credentials["password_hash"])
    return _env_admin_password_hash()


def get_auth_status() -> AuthStatus:
    local_credentials = _fetch_local_credentials()
    if local_credentials is not None:
        return AuthStatus(configured=True, setup_required=False, source="local")

    env_username = _env_admin_username()
    env_password_hash = _env_admin_password_hash()
    if env_username and env_password_hash:
        return AuthStatus(configured=True, setup_required=False, source="environment")

    return AuthStatus(configured=False, setup_required=True, source="none")


def is_admin_auth_configured() -> bool:
    return get_auth_status().configured


def ensure_admin_auth_config(allow_bootstrap: bool = False) -> None:
    status = get_auth_status()
    if not status.configured:
        if allow_bootstrap:
            return
        raise RuntimeError(
            "Admin authentication is not configured. Create credentials from the login screen or set ADMIN_USERNAME and ADMIN_PASSWORD_HASH."
        )

    password_hash = get_admin_password_hash()
    if not _is_valid_bcrypt_hash(password_hash):
        raise RuntimeError("ADMIN_PASSWORD_HASH is not a valid bcrypt hash.")


def setup_admin_credentials(username: str, password: str) -> AuthStatus:
    status = get_auth_status()
    if status.configured:
        raise RuntimeError("Admin credentials are already configured. Use reset instead.")
    _write_local_credentials(username=username, password=password)
    get_session_store().clear_all_sessions()
    return get_auth_status()


def reset_admin_credentials(
    current_username: str,
    new_username: str,
    new_password: str,
) -> AuthStatus:
    expected_username = get_admin_username()
    if not expected_username or not hmac.compare_digest(current_username.strip(), expected_username):
        raise RuntimeError("Current username is incorrect.")
    _write_local_credentials(username=new_username, password=new_password)
    get_session_store().clear_all_sessions()
    return get_auth_status()


def authenticate_admin(username: str, password: str) -> bool:
    init_database()
    expected_username = get_admin_username()
    stored_hash = get_admin_password_hash()
    if not expected_username or not stored_hash:
        return False

    username_ok = hmac.compare_digest(username.strip(), expected_username)
    try:
        password_ok = bcrypt.checkpw(password.encode("utf-8"), stored_hash)
    except ValueError:
        return False
    return username_ok and password_ok
