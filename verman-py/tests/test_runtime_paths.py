import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


import runtime_paths


class RuntimePathsTests(unittest.TestCase):
    def test_find_packaged_executable_prefers_frozen_runtime_executable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            exe_path = Path(temp_dir) / "VersionManager.exe"
            exe_path.write_bytes(b"exe")

            with mock.patch.object(runtime_paths.sys, "frozen", True, create=True):
                with mock.patch.object(runtime_paths.sys, "executable", str(exe_path)):
                    resolved = runtime_paths.find_packaged_executable()

            self.assertEqual(resolved, str(exe_path.resolve()))

    def test_find_packaged_executable_falls_back_to_dist_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dist_dir = root / "dist"
            dist_dir.mkdir()
            exe_path = dist_dir / "VersionManager.exe"
            exe_path.write_bytes(b"exe")

            with mock.patch.object(runtime_paths.sys, "frozen", False, create=True):
                resolved = runtime_paths.find_packaged_executable(search_roots=[root])

            self.assertEqual(resolved, str(exe_path.resolve()))
