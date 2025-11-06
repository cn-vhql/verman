"""
项目管理模块
负责项目的创建、打开、关闭等管理操作
"""

import os
from typing import Optional
from database import DatabaseManager
from file_manager import FileManager


class ProjectManager:
    """项目管理器，负责项目的生命周期管理"""

    def __init__(self):
        """初始化项目管理器"""
        self.current_project_path: Optional[str] = None
        self.db_manager: Optional[DatabaseManager] = None
        self.file_manager: Optional[FileManager] = None

    def create_project(self, workspace_path: str) -> bool:
        """
        创建新项目

        Args:
            workspace_path: 工作区路径

        Returns:
            创建是否成功
        """
        try:
            workspace_path = os.path.abspath(workspace_path)

            # 检查目录是否存在
            if not os.path.exists(workspace_path):
                return False

            # 检查是否已经是项目
            db_path = os.path.join(workspace_path, '.verman.db')
            if os.path.exists(db_path):
                return False

            # 创建忽略文件
            self._create_ignore_file(workspace_path)

            # 创建数据库
            self.db_manager = DatabaseManager(db_path)

            # 设置项目配置
            self.db_manager.set_config('project_path', workspace_path)
            self.db_manager.set_config('create_time', self._get_current_time())

            # 初始化文件管理器
            self.file_manager = FileManager(workspace_path)

            # 保存当前项目路径
            self.current_project_path = workspace_path

            return True

        except Exception as e:
            print(f"创建项目失败: {e}")
            return False

    def open_project(self, workspace_path: str) -> bool:
        """
        打开现有项目

        Args:
            workspace_path: 工作区路径

        Returns:
            打开是否成功
        """
        try:
            workspace_path = os.path.abspath(workspace_path)

            # 检查目录是否存在
            if not os.path.exists(workspace_path):
                return False

            # 检查项目数据库是否存在
            db_path = os.path.join(workspace_path, '.verman.db')
            if not os.path.exists(db_path):
                return False

            # 打开数据库
            self.db_manager = DatabaseManager(db_path)

            # 验证项目路径是否匹配
            stored_path = self.db_manager.get_config('project_path')
            if stored_path and stored_path != workspace_path:
                print(f"警告: 存储的项目路径({stored_path})与当前路径({workspace_path})不匹配")

            # 初始化文件管理器
            self.file_manager = FileManager(workspace_path)

            # 保存当前项目路径
            self.current_project_path = workspace_path

            return True

        except Exception as e:
            print(f"打开项目失败: {e}")
            return False

    def close_project(self):
        """关闭当前项目"""
        if self.db_manager:
            self.db_manager.close()
            self.db_manager = None

        self.file_manager = None
        self.current_project_path = None

    def delete_project(self, workspace_path: str) -> bool:
        """
        删除项目（仅删除数据库文件，不影响工作文件）

        Args:
            workspace_path: 工作区路径

        Returns:
            删除是否成功
        """
        try:
            workspace_path = os.path.abspath(workspace_path)
            db_path = os.path.join(workspace_path, '.verman.db')

            if not os.path.exists(db_path):
                return False

            # 如果当前项目是要删除的项目，先关闭
            if self.current_project_path == workspace_path:
                self.close_project()

            # 删除数据库文件
            os.remove(db_path)

            return True

        except Exception as e:
            print(f"删除项目失败: {e}")
            return False

    def is_project_open(self) -> bool:
        """检查是否有项目已打开"""
        return self.current_project_path is not None and self.db_manager is not None

    def get_current_project_path(self) -> Optional[str]:
        """获取当前项目路径"""
        return self.current_project_path

    def get_database_manager(self) -> Optional[DatabaseManager]:
        """获取数据库管理器"""
        return self.db_manager

    def get_file_manager(self) -> Optional[FileManager]:
        """获取文件管理器"""
        return self.file_manager

    def get_project_info(self) -> Optional[dict]:
        """获取当前项目信息"""
        if not self.is_project_open():
            return None

        try:
            config = {
                'project_path': self.db_manager.get_config('project_path'),
                'create_time': self.db_manager.get_config('create_time'),
            }

            # 获取版本统计信息
            versions = self.db_manager.get_all_versions()
            config['version_count'] = len(versions)

            if versions:
                config['latest_version'] = versions[0]['version_number']
                config['latest_time'] = versions[0]['create_time']
            else:
                config['latest_version'] = '无'
                config['latest_time'] = '无'

            return config

        except Exception as e:
            print(f"获取项目信息失败: {e}")
            return None

    def _create_ignore_file(self, workspace_path: str):
        """
        创建基础的忽略文件

        Args:
            workspace_path: 工作区路径
        """
        try:
            ignore_file_path = os.path.join(workspace_path, '.vermanignore')

            # 如果文件已存在，不覆盖
            if os.path.exists(ignore_file_path):
                return

            # 定义基础忽略规则
            ignore_content = """# VerMan 忽略文件
# 此文件用于指定版本管理中需要忽略的文件和目录

# 版本管理数据库
.verman.db
.verman_backup/

# Python 相关
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# 虚拟环境
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

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

# 编译文件
*.o
*.obj
*.exe
*.dll
*.class

# 压缩文件
*.zip
*.tar.gz
*.rar

# 文档缓存
*.aux
*.toc
*.out
*.bbl
*.blg
"""

            with open(ignore_file_path, 'w', encoding='utf-8') as f:
                f.write(ignore_content)

        except Exception as e:
            print(f"创建忽略文件失败: {e}")

    def _get_current_time(self) -> str:
        """获取当前时间字符串"""
        from datetime import datetime
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def __del__(self):
        """析构函数，确保数据库连接关闭"""
        self.close_project()