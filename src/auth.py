import os

from src.db import init_database


DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"


def get_admin_credentials() -> tuple[str, str]:
    username = os.getenv("ATTENDANCE_ADMIN_USERNAME", DEFAULT_ADMIN_USERNAME)
    password = os.getenv("ATTENDANCE_ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)
    return username, password


def authenticate_admin(username: str, password: str) -> bool:
    init_database()
    expected_username, expected_password = get_admin_credentials()
    return username == expected_username and password == expected_password

