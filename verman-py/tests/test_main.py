import importlib
import os
import sys
import types
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


class DummyGUI:
    instances = []

    def __init__(self, startup_path=None):
        self.startup_path = startup_path
        self.run_called = False
        DummyGUI.instances.append(self)

    def run(self):
        self.run_called = True


class MainEntrypointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_gui_module = sys.modules.get("gui")
        gui_module = types.ModuleType("gui")
        gui_module.VersionManagerGUI = DummyGUI
        sys.modules["gui"] = gui_module
        sys.modules.pop("main", None)
        cls.main_module = importlib.import_module("main")

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop("main", None)
        if cls.original_gui_module is not None:
            sys.modules["gui"] = cls.original_gui_module
        else:
            sys.modules.pop("gui", None)

    def setUp(self):
        DummyGUI.instances.clear()

    def test_parse_startup_path_defaults_to_none(self):
        self.assertIsNone(self.main_module.parse_startup_path([]))

    def test_parse_startup_path_accepts_single_argument(self):
        self.assertEqual(
            self.main_module.parse_startup_path([r"C:\workspace\demo.txt"]),
            r"C:\workspace\demo.txt",
        )

    def test_main_passes_startup_path_to_gui(self):
        self.main_module.main([r"C:\workspace"])
        self.assertEqual(len(DummyGUI.instances), 1)
        self.assertEqual(DummyGUI.instances[0].startup_path, r"C:\workspace")
        self.assertTrue(DummyGUI.instances[0].run_called)
