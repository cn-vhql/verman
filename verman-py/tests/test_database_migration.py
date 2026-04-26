import glob
import hashlib
import os
import sqlite3
import sys
import tempfile
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


from models import CURRENT_SCHEMA_VERSION
from project_manager import ProjectManager
from project_paths import (
    get_metadata_dir,
    get_project_database_path,
    get_legacy_database_path,
)
from version_manager import VersionManager


class DatabaseMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = self.temp_dir.name
        self.db_path = get_legacy_database_path(self.workspace)
        self.legacy_content = b"legacy version content"
        self.manager = None
        self._write_file("legacy.txt", self.legacy_content)
        self._create_legacy_database()

    def tearDown(self):
        if self.manager is not None:
            self.manager.close_project()
        self.temp_dir.cleanup()

    def test_open_project_backs_up_and_migrates_legacy_database(self):
        self.manager = ProjectManager()
        self.assertTrue(self.manager.open_project(self.workspace))

        migrated_db_path = get_project_database_path(self.workspace)
        self.assertTrue(os.path.isdir(get_metadata_dir(self.workspace)))
        self.assertTrue(os.path.exists(migrated_db_path))
        self.assertFalse(os.path.exists(self.db_path))

        backup_paths = glob.glob(f"{migrated_db_path}.bak.*")
        self.assertEqual(len(backup_paths), 1)
        self.assertTrue(os.path.exists(backup_paths[0]))

        db_manager = self.manager.get_database_manager()
        self.assertIsNotNone(db_manager)
        self.assertEqual(db_manager.get_config("schema_version"), CURRENT_SCHEMA_VERSION)
        self.assertEqual(db_manager.get_workspace_index(), {})

        effective_files = db_manager.get_effective_version_files(1)
        self.assertEqual(len(effective_files), 1)
        self.assertEqual(effective_files[0]["relative_path"], "legacy.txt")
        self.assertEqual(effective_files[0]["file_content"], self.legacy_content)

        with open(os.path.join(self.workspace, "legacy.txt"), "wb") as file_handle:
            file_handle.write(b"mutated")

        version_manager = VersionManager(db_manager, self.manager.get_file_manager())
        result = version_manager.rollback_to_version(1, backup_current=False)
        self.assertTrue(result.success, msg=result.error)

        with open(os.path.join(self.workspace, "legacy.txt"), "rb") as file_handle:
            self.assertEqual(file_handle.read(), self.legacy_content)

    def _create_legacy_database(self):
        content_hash = hashlib.md5(self.legacy_content).hexdigest()
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                CREATE TABLE config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version_number TEXT UNIQUE NOT NULL,
                    create_time TEXT NOT NULL,
                    description TEXT,
                    change_count INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version_id INTEGER NOT NULL,
                    relative_path TEXT NOT NULL,
                    file_hash TEXT NOT NULL,
                    file_content BLOB
                )
                """
            )
            conn.execute(
                "INSERT INTO config (key, value) VALUES (?, ?)",
                ("project_path", self.workspace),
            )
            conn.execute(
                "INSERT INTO config (key, value) VALUES (?, ?)",
                ("create_time", "2026-04-26 00:00:00"),
            )
            conn.execute(
                """
                INSERT INTO versions (id, version_number, create_time, description, change_count)
                VALUES (1, 'v1.0', '2026-04-26 00:00:00', 'legacy', 1)
                """
            )
            conn.execute(
                """
                INSERT INTO files (version_id, relative_path, file_hash, file_content)
                VALUES (?, ?, ?, ?)
                """,
                (1, "legacy.txt", content_hash, self.legacy_content),
            )
            conn.commit()
        finally:
            conn.close()

    def _write_file(self, relative_path, content):
        file_path = os.path.join(self.workspace, relative_path)
        parent = os.path.dirname(file_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(file_path, "wb") as file_handle:
            file_handle.write(content)
