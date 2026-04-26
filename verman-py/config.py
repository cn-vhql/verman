"""
Application configuration storage for VerMan.
"""

import json
import os
from typing import Any, Dict, List

from logger import logger as app_logger


DEFAULT_CONFIG = {
    "recent_projects": [],
    "window_geometry": "",
    "ignore_patterns": [
        "*.log",
        "*.tmp",
        "*.temp",
        "__pycache__/",
        "*.pyc",
        ".git/",
        ".svn/",
        ".hg/",
        ".DS_Store",
        "Thumbs.db",
        ".verman/",
        ".verman_backup/",
        ".verman_temp/",
        ".verman.db.bak.*",
    ],
    "auto_backup": True,
}


class ConfigManager:
    """Load and persist user-level configuration."""

    def __init__(self):
        self.config_file = os.path.join(os.path.expanduser("~"), ".verman_config.json")
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        config = dict(DEFAULT_CONFIG)
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as file_handle:
                    loaded_config = json.load(file_handle)
                config.update(loaded_config)

            # Drop legacy settings that are no longer used.
            config.pop("max_versions_in_memory", None)
            return config
        except Exception as exc:
            app_logger.warning(f"加载配置失败，使用默认值: {exc}")
            return config

    def save_config(self):
        try:
            with open(self.config_file, "w", encoding="utf-8") as file_handle:
                json.dump(self.config, file_handle, indent=2, ensure_ascii=False)
        except Exception as exc:
            app_logger.error(f"保存配置失败: {exc}")

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def set(self, key: str, value: Any):
        self.config[key] = value
        self.save_config()

    def add_recent_project(self, project_path: str):
        recent_projects = self.get("recent_projects", [])
        recent_projects = [path for path in recent_projects if path != project_path]
        recent_projects.insert(0, project_path)
        self.set("recent_projects", recent_projects[:10])

    def get_recent_projects(self) -> List[str]:
        return self.get("recent_projects", [])

    def get_ignore_patterns(self) -> List[str]:
        return self.get("ignore_patterns", [])

    def set_ignore_patterns(self, patterns: List[str]):
        self.set("ignore_patterns", patterns)

    def set_window_geometry(self, geometry: str):
        self.set("window_geometry", geometry)

    def get_window_geometry(self) -> str:
        return self.get("window_geometry", "")

    def is_auto_backup_enabled(self) -> bool:
        return self.get("auto_backup", True)

    def set_auto_backup(self, enabled: bool):
        self.set("auto_backup", enabled)

    def reset_to_defaults(self):
        self.config = dict(DEFAULT_CONFIG)
        self.save_config()


config_manager = ConfigManager()
