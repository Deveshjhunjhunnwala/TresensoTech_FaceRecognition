from __future__ import annotations

from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

import src.auth as auth
import src.db as attendance_db
import src.session_store as session_store


class ResetCredentialsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_path = Path(self.temp_dir.name)
        self.original_attendance_db = attendance_db.DATABASE_FILE
        self.original_session_db = session_store.SESSION_DB_FILE
        attendance_db.DATABASE_FILE = temp_path / "attendance.db"
        session_store.SESSION_DB_FILE = temp_path / "session_store.db"
        session_store.get_session_store.cache_clear()
        self.env_patcher = patch.dict(
            os.environ,
            {
                "ADMIN_USERNAME": "",
                "ATTENDANCE_ADMIN_USERNAME": "",
                "ADMIN_PASSWORD_HASH": "",
                "ATTENDANCE_ADMIN_PASSWORD_HASH": "",
            },
            clear=False,
        )
        self.env_patcher.start()

    def tearDown(self) -> None:
        self.env_patcher.stop()
        session_store.get_session_store.cache_clear()
        attendance_db.DATABASE_FILE = self.original_attendance_db
        session_store.SESSION_DB_FILE = self.original_session_db
        self.temp_dir.cleanup()

    def test_reset_credentials_accepts_username_without_current_password(self) -> None:
        auth.setup_admin_credentials(username="admin.user", password="OldPassword1!")

        auth.reset_admin_credentials(
            current_username="admin.user",
            new_username="admin.next",
            new_password="NewPassword1!",
        )

        self.assertFalse(auth.authenticate_admin("admin.user", "OldPassword1!"))
        self.assertTrue(auth.authenticate_admin("admin.next", "NewPassword1!"))

    def test_reset_credentials_still_validates_current_username_and_clears_sessions(self) -> None:
        auth.setup_admin_credentials(username="admin.user", password="OldPassword1!")
        store = session_store.get_session_store()
        original_session = store.create_session("admin.user")

        with self.assertRaisesRegex(RuntimeError, "Current username is incorrect."):
            auth.reset_admin_credentials(
                current_username="wrong.user",
                new_username="admin.next",
                new_password="NewPassword1!",
            )

        self.assertIsNotNone(store.get_session(original_session.session_id))

        auth.reset_admin_credentials(
            current_username="admin.user",
            new_username="admin.next",
            new_password="NewPassword1!",
        )

        self.assertIsNone(store.get_session(original_session.session_id))


if __name__ == "__main__":
    unittest.main()
