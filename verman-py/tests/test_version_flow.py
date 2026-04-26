import os
import sys
import tempfile
import unittest
from unittest import mock


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


from database import DatabaseManager
from file_manager import FileManager
from version_manager import VersionManager


class VersionFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = self.temp_dir.name
        self.db_manager = DatabaseManager(os.path.join(self.workspace, ".verman.db"))
        self.file_manager = FileManager(self.workspace)
        self.version_manager = VersionManager(self.db_manager, self.file_manager)

    def tearDown(self):
        self.db_manager.close()
        self.temp_dir.cleanup()

    def test_create_version_accepts_large_files(self):
        self._write_file("small.txt", b"ok")
        with open(os.path.join(self.workspace, "large.bin"), "wb") as file_handle:
            file_handle.truncate((50 * 1024 * 1024) + 1)

        snapshot = self.version_manager.refresh_workspace(force=True)

        self.assertIn("small.txt", snapshot.current_files)
        self.assertIn("large.bin", snapshot.current_files)
        self.assertEqual(snapshot.blocked_files, [])

        result = self.version_manager.create_version("large file", scan_snapshot=snapshot)
        self.assertTrue(result.success, msg=result.error)
        self.assertEqual(result.blocked_files, [])
        version_id = self.db_manager.get_latest_version_id()
        effective_files = {
            file_info["relative_path"]: file_info
            for file_info in self.db_manager.get_effective_version_files(version_id)
        }
        self.assertIn("large.bin", effective_files)
        self.assertEqual(len(effective_files["large.bin"]["file_content"]), (50 * 1024 * 1024) + 1)

    def test_rollback_restores_target_state_and_removes_extra_files(self):
        self._write_file("root.txt", b"v1-root")
        self._write_file("nested/child.txt", b"v1-child")
        first_snapshot = self.version_manager.refresh_workspace(force=True)
        first_result = self.version_manager.create_version("v1", scan_snapshot=first_snapshot)
        self.assertTrue(first_result.success, msg=first_result.error)
        version1_id = self.db_manager.get_latest_version_id()

        self._write_file("root.txt", b"v2-root")
        os.remove(os.path.join(self.workspace, "nested", "child.txt"))
        self._write_file("new.txt", b"v2-new")
        second_snapshot = self.version_manager.refresh_workspace(force=True)
        second_result = self.version_manager.create_version("v2", scan_snapshot=second_snapshot)
        self.assertTrue(second_result.success, msg=second_result.error)

        self._write_file("stray.txt", b"temporary")

        rollback_result = self.version_manager.rollback_to_version(version1_id, backup_current=False)
        self.assertTrue(rollback_result.success, msg=rollback_result.error)

        self.assertEqual(self._read_file("root.txt"), b"v1-root")
        self.assertEqual(self._read_file("nested/child.txt"), b"v1-child")
        self.assertFalse(os.path.exists(os.path.join(self.workspace, "new.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.workspace, "stray.txt")))

    def test_effective_version_rebuild_preserves_content_for_unmodified_rows(self):
        self._write_file("a.txt", b"version-1-a")
        self._write_file("b.txt", b"version-1-b")
        snapshot1 = self.version_manager.refresh_workspace(force=True)
        result1 = self.version_manager.create_version("v1", scan_snapshot=snapshot1)
        self.assertTrue(result1.success, msg=result1.error)

        self._write_file("a.txt", b"version-2-a")
        snapshot2 = self.version_manager.refresh_workspace(force=True)
        result2 = self.version_manager.create_version("v2", scan_snapshot=snapshot2)
        self.assertTrue(result2.success, msg=result2.error)

        latest_version_id = self.db_manager.get_latest_version_id()
        effective_files = {
            file_info["relative_path"]: file_info
            for file_info in self.db_manager.get_effective_version_files(latest_version_id)
        }

        self.assertEqual(effective_files["a.txt"]["file_status"], "modify")
        self.assertEqual(effective_files["a.txt"]["file_content"], b"version-2-a")
        self.assertEqual(effective_files["b.txt"]["file_status"], "unmodified")
        self.assertEqual(effective_files["b.txt"]["file_content"], b"version-1-b")

    def test_incremental_scan_reuses_indexed_hashes(self):
        self._write_file("indexed.txt", b"initial")
        current_files, blocked_files = self.file_manager.scan_workspace([], {})
        self.assertEqual(blocked_files, [])
        self.db_manager.update_workspace_index(current_files.values(), 1)
        indexed_files = self.db_manager.get_workspace_index()

        with mock.patch.object(
            self.file_manager,
            "_calculate_file_hash",
            side_effect=AssertionError("hash should be reused"),
        ):
            reused_files, blocked_files = self.file_manager.scan_workspace([], indexed_files)

        self.assertEqual(blocked_files, [])
        self.assertEqual(reused_files["indexed.txt"].file_hash, current_files["indexed.txt"].file_hash)

        self._write_file("indexed.txt", b"changed")
        indexed_files = self.db_manager.get_workspace_index()
        original_hash = FileManager._calculate_file_hash
        with mock.patch.object(
            self.file_manager,
            "_calculate_file_hash",
            wraps=original_hash.__get__(self.file_manager, FileManager),
        ) as hash_mock:
            changed_files, blocked_files = self.file_manager.scan_workspace([], indexed_files)

        self.assertEqual(blocked_files, [])
        self.assertEqual(hash_mock.call_count, 1)
        self.assertNotEqual(
            changed_files["indexed.txt"].file_hash,
            current_files["indexed.txt"].file_hash,
        )

    def test_create_version_uses_scan_snapshot_without_second_rescan(self):
        self._write_file("once.txt", b"snapshot")
        snapshot = self.version_manager.refresh_workspace(force=True)

        with mock.patch.object(
            self.version_manager,
            "refresh_workspace",
            side_effect=AssertionError("refresh should not be called"),
        ):
            result = self.version_manager.create_version("v1", scan_snapshot=snapshot)

        self.assertTrue(result.success, msg=result.error)

    def _write_file(self, relative_path, content):
        file_path = os.path.join(self.workspace, relative_path)
        parent = os.path.dirname(file_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(file_path, "wb") as file_handle:
            file_handle.write(content)

    def _read_file(self, relative_path):
        with open(os.path.join(self.workspace, relative_path), "rb") as file_handle:
            return file_handle.read()
