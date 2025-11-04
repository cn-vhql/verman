"""
版本存储管理类
"""
import json
import os
import shutil
from typing import Dict, List, Optional, Set
from datetime import datetime

from ..core.models import Repository, VersionInfo


class VersionStorage:
    """版本存储管理类"""

    def __init__(self, repository: Repository):
        self.repo = repository

    def initialize_storage(self) -> bool:
        """初始化版本存储结构"""
        try:
            os.makedirs(self.repo.svmini_path, exist_ok=True)
            os.makedirs(self.repo.versions_path, exist_ok=True)
            os.makedirs(self.repo.backups_path, exist_ok=True)
            return True
        except Exception:
            return False

    def get_next_version_number(self) -> int:
        """获取下一个版本号"""
        if not os.path.exists(self.repo.versions_path):
            return 1

        version_dirs = [d for d in os.listdir(self.repo.versions_path)
                       if d.isdigit() and os.path.isdir(os.path.join(self.repo.versions_path, d))]

        if not version_dirs:
            return 1

        max_version = max(int(d) for d in version_dirs)
        return max_version + 1

    def save_version(self, version_info: VersionInfo, files_data: Dict[str, bytes]) -> bool:
        """保存版本"""
        try:
            version_path = self.repo.get_version_path(version_info.version)
            files_path = self.repo.get_version_files_path(version_info.version)
            meta_path = self.repo.get_version_meta_path(version_info.version)

            # 创建版本目录
            os.makedirs(files_path, exist_ok=True)

            # 保存文件
            for relative_path, content in files_data.items():
                file_storage_path = os.path.join(files_path, relative_path)
                os.makedirs(os.path.dirname(file_storage_path), exist_ok=True)

                with open(file_storage_path, 'wb') as f:
                    f.write(content)

            # 保存版本元数据
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(version_info.to_dict(), f, indent=2, ensure_ascii=False)

            return True
        except Exception:
            return False

    def load_version(self, version: int) -> Optional[VersionInfo]:
        """加载版本信息"""
        meta_path = self.repo.get_version_meta_path(version)
        if not os.path.exists(meta_path):
            return None

        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return VersionInfo.from_dict(data)
        except Exception:
            return None

    def get_version_list(self) -> List[VersionInfo]:
        """获取所有版本列表"""
        versions = []
        if not os.path.exists(self.repo.versions_path):
            return versions

        try:
            for item in os.listdir(self.repo.versions_path):
                item_path = os.path.join(self.repo.versions_path, item)
                if os.path.isdir(item_path) and item.isdigit():
                    version = int(item)
                    version_info = self.load_version(version)
                    if version_info:
                        versions.append(version_info)

            # 按版本号排序
            versions.sort(key=lambda v: v.version, reverse=True)
        except Exception:
            pass

        return versions

    def get_file_content(self, version: int, relative_path: str) -> Optional[bytes]:
        """获取指定版本的文件内容"""
        file_path = os.path.join(self.repo.get_version_files_path(version), relative_path)
        if not os.path.exists(file_path):
            return None

        try:
            with open(file_path, 'rb') as f:
                return f.read()
        except Exception:
            return None

    def restore_file(self, version: int, relative_path: str, target_path: str) -> bool:
        """恢复指定版本的文件到目标路径"""
        content = self.get_file_content(version, relative_path)
        if content is None:
            return False

        try:
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, 'wb') as f:
                f.write(content)
            return True
        except Exception:
            return False