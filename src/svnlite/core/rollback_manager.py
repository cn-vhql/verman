"""
版本回滚管理类
"""
import os
import shutil
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from .models import Repository, VersionInfo, FileInfo, FileStatus
from svnlite.utils.file_utils import safe_remove_file, copy_file_with_permissions, ensure_directory_exists


class RollbackManager:
    """版本回滚管理类"""

    def __init__(self, repository: Repository, storage, file_tracker):
        self.repository = repository
        self.storage = storage
        self.file_tracker = file_tracker

    def rollback_to_version(self, target_version: int, create_backup: bool = True) -> Tuple[bool, str]:
        """回滚到指定版本"""
        if not self.repository.is_repository():
            return False, "当前目录不是版本库"

        # 验证目标版本
        target_version_info = self.storage.load_version(target_version)
        if not target_version_info:
            return False, f"版本 {target_version} 不存在"

        current_version = self._get_current_version()
        if target_version == current_version:
            return False, "当前版本与目标版本相同，无需回滚"

        try:
            # 获取将被覆盖的文件列表
            modified_files = self.file_tracker.get_modified_files()
            affected_files = list(modified_files.keys())

            # 执行回滚
            success_count = 0

            # 1. 恢复目标版本的文件
            for relative_path in target_version_info.added_files + target_version_info.modified_files:
                abs_path = self.repository.get_file_path(relative_path)
                if self.storage.restore_file(target_version, relative_path, abs_path):
                    success_count += 1

            # 2. 删除在目标版本之后添加的文件
            current_version_info = self.storage.load_version(current_version)
            if current_version_info:
                for relative_path in current_version_info.added_files:
                    if relative_path not in target_version_info.added_files:
                        abs_path = self.repository.get_file_path(relative_path)
                        if safe_remove_file(abs_path):
                            success_count += 1

            # 3. 恢复在目标版本之后删除的文件
            for relative_path in target_version_info.deleted_files:
                abs_path = self.repository.get_file_path(relative_path)
                if self.storage.restore_file(target_version, relative_path, abs_path):
                    success_count += 1

            # 更新文件索引
            if not self._update_index_to_version(target_version):
                return False, "更新文件索引失败"

            # 清除缓存
            self.file_tracker.clear_cache()

            result_msg = f"回滚完成！成功处理 {success_count} 个文件"
            return True, result_msg

        except Exception as e:
            return False, f"回滚失败: {str(e)}"

    def _get_current_version(self) -> int:
        """获取当前版本号"""
        try:
            index = self.file_tracker._load_index()
            return index.get("last_version", 0)
        except Exception:
            return 0

    def _update_index_to_version(self, target_version: int) -> bool:
        """将文件索引更新到指定版本"""
        try:
            # 获取目标版本信息
            version_info = self.storage.load_version(target_version)
            if not version_info:
                return False

            # 构建目标版本的文件索引
            index = {"files": {}, "last_version": target_version}

            # 从历史版本构建文件列表
            for v in range(1, target_version + 1):
                v_info = self.storage.load_version(v)
                if v_info:
                    for relative_path in v_info.added_files:
                        file_content = self.storage.get_file_content(v, relative_path)
                        if file_content:
                            import hashlib
                            file_hash = hashlib.sha256(file_content).hexdigest()
                            index["files"][relative_path] = {
                                "hash": file_hash,
                                "size": len(file_content),
                                "version": v
                            }

                    for relative_path in v_info.modified_files:
                        file_content = self.storage.get_file_content(v, relative_path)
                        if file_content:
                            import hashlib
                            file_hash = hashlib.sha256(file_content).hexdigest()
                            index["files"][relative_path] = {
                                "hash": file_hash,
                                "size": len(file_content),
                                "version": v
                            }

                    for relative_path in v_info.deleted_files:
                        if relative_path in index["files"]:
                            del index["files"][relative_path]

            return self.file_tracker._save_index()

        except Exception:
            return False