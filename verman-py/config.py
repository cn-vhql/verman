"""
配置管理模块
负责应用程序配置的读取和保存
"""

import os
import json
from typing import Dict, Any, List


class ConfigManager:
    """配置管理器"""

    def __init__(self):
        """初始化配置管理器"""
        self.config_file = os.path.join(os.path.expanduser("~"), ".verman_config.json")
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        default_config = {
            "recent_projects": [],
            "window_geometry": "",
            "ignore_patterns": [
                "*.log", "*.tmp", "*.temp", "__pycache__", "*.pyc",
                ".git", ".svn", ".hg", ".DS_Store", "Thumbs.db",
                ".verman_backup", ".verman_temp"
            ],
            "auto_backup": True,
            "max_versions_in_memory": 100
        }

        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # 合并默认配置和加载的配置
                    default_config.update(loaded_config)
            return default_config
        except Exception:
            return default_config

    def save_config(self):
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存配置失败: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        return self.config.get(key, default)

    def set(self, key: str, value: Any):
        """设置配置项"""
        self.config[key] = value
        self.save_config()

    def add_recent_project(self, project_path: str):
        """添加最近项目"""
        recent_projects = self.get("recent_projects", [])

        # 移除已存在的相同路径
        recent_projects = [p for p in recent_projects if p != project_path]

        # 添加到开头
        recent_projects.insert(0, project_path)

        # 限制数量
        recent_projects = recent_projects[:10]

        self.set("recent_projects", recent_projects)

    def get_recent_projects(self) -> List[str]:
        """获取最近项目列表"""
        return self.get("recent_projects", [])

    def get_ignore_patterns(self) -> List[str]:
        """获取忽略文件模式"""
        return self.get("ignore_patterns", [])

    def set_ignore_patterns(self, patterns: List[str]):
        """设置忽略文件模式"""
        self.set("ignore_patterns", patterns)

    def set_window_geometry(self, geometry: str):
        """设置窗口几何信息"""
        self.set("window_geometry", geometry)

    def get_window_geometry(self) -> str:
        """获取窗口几何信息"""
        return self.get("window_geometry", "")

    def is_auto_backup_enabled(self) -> bool:
        """是否启用自动备份"""
        return self.get("auto_backup", True)

    def set_auto_backup(self, enabled: bool):
        """设置自动备份"""
        self.set("auto_backup", enabled)

    def get_max_versions_in_memory(self) -> int:
        """获取内存中最大版本数"""
        return self.get("max_versions_in_memory", 100)

    def set_max_versions_in_memory(self, count: int):
        """设置内存中最大版本数"""
        self.set("max_versions_in_memory", count)

    def reset_to_defaults(self):
        """重置配置到默认值"""
        default_config = {
            "recent_projects": [],
            "window_geometry": "",
            "ignore_patterns": [
                "*.log", "*.tmp", "*.temp", "__pycache__", "*.pyc",
                ".git", ".svn", ".hg", ".DS_Store", "Thumbs.db",
                ".verman_backup", ".verman_temp"
            ],
            "auto_backup": True,
            "max_versions_in_memory": 100
        }
        self.config = default_config
        self.save_config()


# 全局配置管理器实例
config_manager = ConfigManager()