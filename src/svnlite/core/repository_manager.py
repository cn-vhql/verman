"""
版本库管理类
"""
import os
import json
from typing import Optional, List, Tuple
from datetime import datetime

from .models import Repository, Config, IgnoreRules


class RepositoryManager:
    """版本库管理类"""

    def __init__(self, root_path: str):
        self.repository = Repository(root_path)
        self.ignore_rules = IgnoreRules(root_path)

    def initialize_repository(self, author: Optional[str] = None) -> Tuple[bool, str]:
        """初始化版本库"""
        # 检查是否已经是版本库
        if self.repository.is_repository():
            return False, "该文件夹已经是版本库，无需重复初始化"

        # 检查目录权限
        if not os.access(self.repository.root_path, os.W_OK):
            return False, "无写入权限，请选择其他文件夹"

        try:
            # 创建版本库目录结构
            if not self._create_storage_structure():
                return False, "创建版本库目录失败"

            # 创建默认配置
            config = Config()
            if author:
                config.author = author
            if not self._save_config(config):
                return False, "创建配置文件失败"

            # 创建默认忽略文件
            self._create_default_ignore_file()

            # 创建初始索引文件
            index_data = {"files": {}, "last_version": 0}
            with open(self.repository.index_path, 'w', encoding='utf-8') as f:
                json.dump(index_data, f, indent=2, ensure_ascii=False)

            return True, "版本库初始化成功"

        except Exception as e:
            return False, f"初始化失败: {str(e)}"

    def _create_storage_structure(self) -> bool:
        """创建版本存储结构"""
        try:
            os.makedirs(self.repository.svmini_path, exist_ok=True)
            os.makedirs(self.repository.versions_path, exist_ok=True)
            os.makedirs(self.repository.backups_path, exist_ok=True)
            return True
        except Exception:
            return False

    def _save_config(self, config: Config) -> bool:
        """保存配置"""
        try:
            with open(self.repository.config_path, 'w', encoding='utf-8') as f:
                json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def _create_default_ignore_file(self):
        """创建默认忽略文件"""
        default_ignore_rules = [
            "# 操作系统生成文件",
            ".DS_Store",
            "Thumbs.db",
            "Desktop.ini",
            "",
            "# 临时文件",
            "*.tmp",
            "*.temp",
            "*.log",
            "*.bak",
            "*.swp",
            "*.swo",
            "",
            "# IDE/编辑器文件",
            ".vscode/",
            ".idea/",
            "*.sublime-*",
            "*.iml",
            "",
            "# Python相关",
            "__pycache__/",
            "*.pyc",
            "*.pyo",
            "*.pyd",
            ".python-version",
            "venv/",
            "env/",
            ".env",
            "",
            "# 版本控制文件",
            ".git/",
            ".svn/",
            ".hg/",
            "",
            "# 构建输出",
            "dist/",
            "build/",
            "out/",
            "bin/",
        ]

        ignore_file_path = os.path.join(self.repository.root_path, '.svminiignore')
        with open(ignore_file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(default_ignore_rules))

        self.ignore_rules.load_rules()

    def open_repository(self) -> Tuple[bool, str]:
        """打开现有版本库"""
        if not self.repository.is_repository():
            return False, "该目录不是有效的版本库"

        # 验证版本库完整性
        if not self._validate_repository():
            return False, "版本库文件损坏，无法打开"

        return True, "版本库打开成功"

    def _validate_repository(self) -> bool:
        """验证版本库完整性"""
        try:
            # 检查必要文件是否存在
            required_files = [
                self.repository.config_path,
                self.repository.index_path
            ]

            for file_path in required_files:
                if not os.path.exists(file_path):
                    return False

            # 验证配置文件格式
            try:
                with open(self.repository.config_path, 'r', encoding='utf-8') as f:
                    json.load(f)
            except json.JSONDecodeError:
                return False

            # 验证索引文件格式
            try:
                with open(self.repository.index_path, 'r', encoding='utf-8') as f:
                    json.load(f)
            except json.JSONDecodeError:
                return False

            return True
        except Exception:
            return False