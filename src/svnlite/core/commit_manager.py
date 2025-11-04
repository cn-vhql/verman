"""
版本提交管理类
"""
import os
import json
from typing import Dict, List, Optional, Tuple, Set
from datetime import datetime

from .models import Repository, VersionInfo, FileInfo, FileStatus
from svnlite.utils.file_utils import calculate_file_hash, get_file_size, get_file_mtime


class CommitManager:
    """版本提交管理类"""

    def __init__(self, repository: Repository, file_tracker, storage, config_manager):
        self.repository = repository
        self.file_tracker = file_tracker
        self.storage = storage
        self.config_manager = config_manager

    def prepare_commit(self, selected_files: Optional[List[str]] = None) -> Tuple[bool, str, List[str]]:
        """准备提交，检查待提交的文件"""
        if not self.repository.is_repository():
            return False, "当前目录不是版本库", []

        # 获取已修改的文件
        modified_files = self.file_tracker.get_modified_files()

        if not modified_files:
            return False, "没有待提交的变更文件", []

        # 如果指定了文件列表，只处理这些文件
        if selected_files:
            commit_files = []
            for file_path in selected_files:
                relative_path = self.repository.get_relative_path(file_path) if os.path.isabs(file_path) else file_path
                if relative_path in modified_files:
                    commit_files.append(relative_path)
        else:
            commit_files = list(modified_files.keys())

        if not commit_files:
            return False, "没有可提交的文件", []

        return True, f"准备提交 {len(commit_files)} 个文件", commit_files

    def validate_commit_files(self, file_paths: List[str]) -> Tuple[bool, str, List[FileInfo]]:
        """验证提交文件"""
        valid_files = []
        errors = []

        for relative_path in file_paths:
            file_info = self.file_tracker.get_file_info(relative_path)
            if not file_info:
                errors.append(f"文件不存在: {relative_path}")
                continue

            if file_info.status not in [FileStatus.MODIFIED, FileStatus.ADDED, FileStatus.DELETED]:
                errors.append(f"文件无需提交: {relative_path}")
                continue

            # 检查文件是否可读
            abs_path = self.repository.get_file_path(relative_path)
            if file_info.status != FileStatus.DELETED and not os.path.exists(abs_path):
                errors.append(f"文件不存在或无法访问: {relative_path}")
                continue

            valid_files.append(file_info)

        if errors:
            return False, "\n".join(errors), []

        return True, "文件验证通过", valid_files

    def create_commit(self, message: str, author: Optional[str] = None,
                     selected_files: Optional[List[str]] = None) -> Tuple[bool, str, Optional[int]]:
        """创建提交"""
        if not message or not message.strip():
            return False, "提交信息不能为空", None

        # 准备提交文件
        success, msg, commit_files = self.prepare_commit(selected_files)
        if not success:
            return False, msg, None

        # 验证文件
        success, msg, file_infos = self.validate_commit_files(commit_files)
        if not success:
            return False, msg, None

        # 获取版本号
        current_version = self._get_current_version()
        new_version = current_version + 1

        # 创建版本信息
        version_info = VersionInfo(
            version=new_version,
            timestamp=datetime.now(),
            author=author or self.config_manager.get_author(),
            message=message.strip(),
            added_files=[],
            modified_files=[],
            deleted_files=[],
            parent_version=current_version if current_version > 0 else None
        )

        # 收集文件数据
        files_data = {}
        added_files = []
        modified_files = []
        deleted_files = []

        try:
            for file_info in file_infos:
                relative_path = file_info.path
                abs_path = self.repository.get_file_path(relative_path)

                if file_info.status == FileStatus.DELETED:
                    deleted_files.append(relative_path)
                else:
                    # 读取文件内容
                    with open(abs_path, 'rb') as f:
                        content = f.read()
                    files_data[relative_path] = content

                    # 判断是新增还是修改
                    if not self._is_file_tracked(relative_path):
                        added_files.append(relative_path)
                    else:
                        modified_files.append(relative_path)

            # 更新版本信息
            version_info.added_files = added_files
            version_info.modified_files = modified_files
            version_info.deleted_files = deleted_files

            # 保存版本
            if not self.storage.save_version(version_info, files_data):
                return False, "保存版本失败", None

            # 更新文件索引
            if not self._update_file_index(file_infos, new_version):
                return False, "更新文件索引失败", None

            # 清除缓存
            self.file_tracker.clear_cache()

            return True, f"提交成功！版本号: {new_version}", new_version

        except Exception as e:
            return False, f"提交失败: {str(e)}", None

    def _get_current_version(self) -> int:
        """获取当前版本号"""
        try:
            index = self.file_tracker._load_index()
            return index.get("last_version", 0)
        except Exception:
            return 0

    def _is_file_tracked(self, relative_path: str) -> bool:
        """检查文件是否被追踪"""
        try:
            index = self.file_tracker._load_index()
            tracked_files = index.get("files", {})
            return relative_path in tracked_files
        except Exception:
            return False

    def _update_file_index(self, file_infos: List[FileInfo], new_version: int) -> bool:
        """更新文件索引"""
        try:
            index = self.file_tracker._load_index()
            tracked_files = index.get("files", {})

            for file_info in file_infos:
                relative_path = file_info.path

                if file_info.status == FileStatus.DELETED:
                    # 从追踪列表中移除
                    if relative_path in tracked_files:
                        del tracked_files[relative_path]
                else:
                    # 更新文件信息
                    tracked_files[relative_path] = {
                        "hash": file_info.hash,
                        "size": file_info.size,
                        "mtime": file_info.mtime,
                        "version": new_version
                    }

            index["files"] = tracked_files
            index["last_version"] = new_version

            return self.file_tracker._save_index()

        except Exception:
            return False