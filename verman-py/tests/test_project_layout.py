import os
import sys
import tempfile
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


from project_manager import ProjectManager
from project_paths import (
    get_ignore_file_path,
    get_legacy_database_path,
    get_metadata_dir,
    get_project_database_path,
)


class ProjectLayoutTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = self.temp_dir.name
        self.manager = ProjectManager()

    def tearDown(self):
        self.manager.close_project()
        self.temp_dir.cleanup()

    def test_create_project_stores_metadata_under_verman_directory(self):
        self.assertTrue(self.manager.create_project(self.workspace))

        self.assertTrue(os.path.isdir(get_metadata_dir(self.workspace)))
        self.assertTrue(os.path.exists(get_project_database_path(self.workspace)))
        self.assertTrue(os.path.exists(get_ignore_file_path(self.workspace)))
        self.assertFalse(os.path.exists(get_legacy_database_path(self.workspace)))

    def test_delete_project_removes_metadata_directory_and_keeps_ignore_file(self):
        self.assertTrue(self.manager.create_project(self.workspace))
        self.manager.close_project()

        self.assertTrue(self.manager.delete_project(self.workspace))

        self.assertFalse(os.path.exists(get_project_database_path(self.workspace)))
        self.assertFalse(os.path.isdir(get_metadata_dir(self.workspace)))
        self.assertTrue(os.path.exists(get_ignore_file_path(self.workspace)))
