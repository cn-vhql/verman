"""
文件追踪管理类
"""
import os
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from .models import Repository, FileInfo, FileStatus, IgnoreRules


class FileTracker:
    """文件追踪管理类"""

    def __init__(self, repository: Repository, ignore_rules: IgnoreRules):
        self.repository = repository
        self.ignore_rules = ignore_rules
        self.index_path = repository.index_path
        self._index_cache: Optional[Dict] = None

    def _load_index(self) -> Dict:
        """加载文件索引"""
        if self._index_cache is not None:
            return self._index_cache

        try:
            if os.path.exists(self.index_path):
                with open(self.index_path, 'r', encoding='utf-8') as f:
                    self._index_cache = json.load(f)
            else:
                self._index_cache = {"files": {}, "last_version": 0}
        except Exception:
            self._index_cache = {"files": {}, "last_version": 0}

        return self._index_cache

    def _save_index(self) -> bool:
        """保存文件索引"""
        try:
            with open(self.index_path, 'w', encoding='utf-8') as f:
                json.dump(self._index_cache, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def scan_files(self) -> Dict[str, FileInfo]:
        """扫描工作目录，获取所有文件状态"""
        if not self.repository.is_repository():
            return {}

        index = self._load_index()
        tracked_files = index.get("files", {})

        # 获取工作目录中的所有文件
        from svnlite.utils.file_utils import find_files, calculate_file_hash, get_file_size, get_file_mtime
        all_files = find_files(self.repository.root_path)

        # 创建文件状态字典
        file_status: Dict[str, FileInfo] = {}

        # 处理工作目录中的文件
        for file_path in all_files:
            relative_path = self.repository.get_relative_path(file_path)

            # 跳过.svmini目录和忽略文件
            if relative_path.startswith('.svmini') or self.ignore_rules.is_ignored(file_path):
                continue

            # 获取文件信息
            file_hash = calculate_file_hash(file_path)
            file_size = get_file_size(file_path)
            file_mtime = get_file_mtime(file_path)

            # 确定文件状态
            if relative_path in tracked_files:
                tracked_info = tracked_files[relative_path]
                if file_hash != tracked_info.get("hash"):
                    status = FileStatus.MODIFIED
                else:
                    status = FileStatus.TRACKED
            else:
                status = FileStatus.UNTRACKED

            file_info = FileInfo(
                path=relative_path,
                hash=file_hash,
                size=file_size,
                mtime=file_mtime,
                status=status
            )
            file_status[relative_path] = file_info

        # 检查已删除的文件
        for relative_path in tracked_files:
            if relative_path not in file_status:
                # 文件在索引中但不在工作目录中
                file_info = FileInfo(
                    path=relative_path,
                    hash=tracked_files[relative_path].get("hash", ""),
                    size=tracked_files[relative_path].get("size", 0),
                    mtime=tracked_files[relative_path].get("mtime", 0),
                    status=FileStatus.DELETED
                )
                file_status[relative_path] = file_info

        return file_status

    def add_files(self, file_paths: List[str]) -> Tuple[bool, str, List[str]]:
        """添加文件到追踪列表"""
        if not self.repository.is_repository():
            return False, "当前目录不是版本库", []

        index = self._load_index()
        tracked_files = index.get("files", {})
        added_files = []

        try:
            for file_path in file_paths:
                # 标准化路径
                if not os.path.isabs(file_path):
                    file_path = os.path.abspath(file_path)

                # 检查文件是否存在
                if not os.path.exists(file_path):
                    continue

                # 检查是否在仓库目录内
                if not file_path.startswith(self.repository.root_path):
                    continue

                relative_path = self.repository.get_relative_path(file_path)

                # 跳过.svmini目录和忽略文件
                if relative_path.startswith('.svmini') or self.ignore_rules.is_ignored(file_path):
                    continue

                # 获取文件信息
                from svnlite.utils.file_utils import calculate_file_hash, get_file_size, get_file_mtime
                file_hash = calculate_file_hash(file_path)
                file_size = get_file_size(file_path)
                file_mtime = get_file_mtime(file_path)

                # 添加到追踪列表
                tracked_files[relative_path] = {
                    "hash": file_hash,
                    "size": file_size,
                    "mtime": file_mtime,
                    "added_time": datetime.now().isoformat()
                }
                added_files.append(relative_path)

            # 保存索引
            index["files"] = tracked_files
            if self._save_index():
                return True, f"成功添加 {len(added_files)} 个文件到追踪列表", added_files
            else:
                return False, "保存索引失败", []

        except Exception as e:
            return False, f"添加文件失败: {str(e)}", []

    def get_modified_files(self) -> Dict[str, FileInfo]:
        """获取所有已修改的文件"""
        file_status = self.scan_files()
        return {path: info for path, info in file_status.items()
                if info.status in [FileStatus.MODIFIED, FileStatus.ADDED, FileStatus.DELETED]}

    def get_file_info(self, relative_path: str) -> Optional[FileInfo]:
        """获取指定文件的信息"""
        file_status = self.scan_files()
        return file_status.get(relative_path)

    def clear_cache(self):
        """清除缓存"""
        self._index_cache = None