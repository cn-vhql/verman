"""
Project lifecycle management for VerMan.
"""

import os
import shutil
from datetime import datetime
from typing import Optional

from database import DatabaseManager
from file_manager import FileManager
from logger import logger as app_logger


class ProjectManager:
    """Manage create/open/close/delete operations for a workspace."""

    def __init__(self):
        self.current_project_path: Optional[str] = None
        self.db_manager: Optional[DatabaseManager] = None
        self.file_manager: Optional[FileManager] = None

    def create_project(self, workspace_path: str) -> bool:
        try:
            workspace_path = os.path.abspath(workspace_path)
            if not os.path.isdir(workspace_path):
                return False

            db_path = os.path.join(workspace_path, ".verman.db")
            if os.path.exists(db_path):
                return False

            self._create_ignore_file(workspace_path)
            self.db_manager = DatabaseManager(db_path)
            self.db_manager.set_config("project_path", workspace_path)
            self.db_manager.set_config("create_time", self._get_current_time())

            self.file_manager = FileManager(workspace_path)
            self.current_project_path = workspace_path
            return True
        except Exception as exc:
            app_logger.error(f"创建项目失败: {exc}")
            return False

    def open_project(self, workspace_path: str) -> bool:
        try:
            workspace_path = os.path.abspath(workspace_path)
            if not os.path.isdir(workspace_path):
                return False

            db_path = os.path.join(workspace_path, ".verman.db")
            if not os.path.exists(db_path):
                return False

            if DatabaseManager.requires_migration(db_path):
                self._backup_database(db_path)

            self.db_manager = DatabaseManager(db_path)
            stored_path = self.db_manager.get_config("project_path")
            if stored_path and stored_path != workspace_path:
                app_logger.warning(
                    f"存储的项目路径({stored_path})与当前路径({workspace_path})不匹配"
                )

            self.file_manager = FileManager(workspace_path)
            self.current_project_path = workspace_path
            return True
        except Exception as exc:
            app_logger.error(f"打开项目失败: {exc}")
            return False

    def close_project(self):
        if self.db_manager:
            self.db_manager.close()
            self.db_manager = None

        self.file_manager = None
        self.current_project_path = None

    def delete_project(self, workspace_path: str) -> bool:
        try:
            workspace_path = os.path.abspath(workspace_path)
            db_path = os.path.join(workspace_path, ".verman.db")
            if not os.path.exists(db_path):
                return False

            if self.current_project_path == workspace_path:
                self.close_project()

            os.remove(db_path)
            return True
        except Exception as exc:
            app_logger.error(f"删除项目失败: {exc}")
            return False

    def is_project_open(self) -> bool:
        return self.current_project_path is not None and self.db_manager is not None

    def get_current_project_path(self) -> Optional[str]:
        return self.current_project_path

    def get_database_manager(self) -> Optional[DatabaseManager]:
        return self.db_manager

    def get_file_manager(self) -> Optional[FileManager]:
        return self.file_manager

    def get_project_info(self) -> Optional[dict]:
        if not self.is_project_open():
            return None

        try:
            info = {
                "project_path": self.db_manager.get_config("project_path"),
                "create_time": self.db_manager.get_config("create_time"),
            }

            versions = self.db_manager.get_all_versions()
            info["version_count"] = len(versions)
            if versions:
                info["latest_version"] = versions[0]["version_number"]
                info["latest_time"] = versions[0]["create_time"]
            else:
                info["latest_version"] = "无"
                info["latest_time"] = "无"
            return info
        except Exception as exc:
            app_logger.error(f"获取项目信息失败: {exc}")
            return None

    def _backup_database(self, db_path: str):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{db_path}.bak.{timestamp}"
        shutil.copy2(db_path, backup_path)
        app_logger.info(f"已备份旧数据库: {backup_path}")

    def _create_ignore_file(self, workspace_path: str):
        ignore_file_path = os.path.join(workspace_path, ".vermanignore")
        if os.path.exists(ignore_file_path):
            return

        ignore_content = """# VerMan 忽略文件
# 此文件用于指定版本管理中需要忽略的文件和目录

# 版本管理数据库和备份
.verman.db
.verman.db-shm
.verman.db-wal
.verman.db-journal
.verman.db.bak.*
.verman_backup/

# Python 相关
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
dist/
*.egg-info/
*.egg

# 虚拟环境
.env
.venv/
env/
venv/
ENV/

# IDE 相关
.vscode/
.idea/
*.swp
*.swo
*~

# 系统文件
.DS_Store
Thumbs.db
desktop.ini

# 临时文件
*.tmp
*.temp
*.log
*.bak
*.backup
"""

        with open(ignore_file_path, "w", encoding="utf-8") as file_handle:
            file_handle.write(ignore_content)

    def _get_current_time(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def __del__(self):
        self.close_project()
