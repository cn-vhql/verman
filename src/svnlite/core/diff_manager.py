"""
差异对比管理类
"""
import difflib
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from .models import Repository, FileInfo, FileStatus
from svnlite.utils.file_utils import read_text_file, is_binary_file


@dataclass
class DiffResult:
    """差异结果数据类"""
    file_path: str
    file_type: str  # 'text' or 'binary'
    old_size: int
    new_size: int
    old_hash: str
    new_hash: str
    diff_lines: Optional[List[str]] = None  # 文本文件的差异行
    similarity: float = 0.0                # 相似度


class DiffManager:
    """差异对比管理类"""

    def __init__(self, repository: Repository, storage):
        self.repository = repository
        self.storage = storage

    def compare_working_vs_version(self, version: int, file_path: Optional[str] = None) -> Dict[str, DiffResult]:
        """对比工作目录与指定版本的差异"""
        if not self.repository.is_repository():
            return {}

        # 获取工作目录文件状态
        from .file_tracker import FileTracker
        from .models import IgnoreRules
        file_tracker = FileTracker(self.repository, IgnoreRules(self.repository.root_path))
        working_files = file_tracker.scan_files()

        results = {}

        if file_path:
            # 对比指定文件
            if file_path in working_files:
                result = self._compare_file_with_version(file_path, version, working_files[file_path])
                if result:
                    results[file_path] = result
        else:
            # 对比所有文件
            for relative_path, file_info in working_files.items():
                result = self._compare_file_with_version(relative_path, version, file_info)
                if result:
                    results[relative_path] = result

        return results

    def _compare_file_with_version(self, relative_path: str, version: int, file_info: FileInfo) -> Optional[DiffResult]:
        """对比工作目录文件与指定版本"""
        # 获取指定版本的文件内容
        old_content = self.storage.get_file_content(version, relative_path)
        old_hash = ""
        old_size = 0

        if old_content is not None:
            import hashlib
            old_hash = hashlib.sha256(old_content).hexdigest()
            old_size = len(old_content)

        # 获取工作目录文件信息
        abs_path = self.repository.get_file_path(relative_path)
        new_hash = file_info.hash
        new_size = file_info.size

        # 如果文件状态是删除的
        if file_info.status == FileStatus.DELETED:
            if old_content is None:
                return None  # 两个版本都不存在
            return DiffResult(
                file_path=relative_path,
                file_type='binary' if is_binary_file(abs_path) else 'text',
                old_size=old_size,
                new_size=0,
                old_hash=old_hash,
                new_hash="",
                similarity=0.0
            )

        # 如果文件是新添加的
        if not self.storage.get_file_content(version, relative_path):
            try:
                with open(abs_path, 'rb') as f:
                    new_content = f.read()
            except Exception:
                return None

            return DiffResult(
                file_path=relative_path,
                file_type='binary' if is_binary_file(abs_path) else 'text',
                old_size=0,
                new_size=new_size,
                old_hash="",
                new_hash=new_hash,
                similarity=0.0
            )

        # 文件在两个版本都存在
        if old_hash == new_hash:
            return None  # 文件没有变化

        return self._create_diff_result(relative_path, old_content, new_size, new_hash)

    def _create_diff_result(self, relative_path: str, old_content: Optional[bytes],
                           new_size: int, new_hash: str) -> Optional[DiffResult]:
        """创建差异结果"""
        abs_path = self.repository.get_file_path(relative_path)

        # 获取新文件内容
        new_content = None
        if os.path.exists(abs_path):
            try:
                with open(abs_path, 'rb') as f:
                    new_content = f.read()
            except Exception:
                pass

        if not new_content:
            return None

        # 判断文件类型
        is_binary = is_binary_file(abs_path)

        if is_binary:
            # 二进制文件
            return DiffResult(
                file_path=relative_path,
                file_type='binary',
                old_size=len(old_content) if old_content else 0,
                new_size=new_size,
                old_hash=hashlib.sha256(old_content).hexdigest() if old_content else "",
                new_hash=new_hash,
                similarity=self._calculate_binary_similarity(old_content, new_content)
            )
        else:
            # 文本文件
            old_text = read_text_file(abs_path) if old_content else ""
            new_text = read_text_file(abs_path)

            if old_text is None or new_text is None:
                return None

            # 生成差异
            diff_lines = list(difflib.unified_diff(
                old_text.splitlines(keepends=True),
                new_text.splitlines(keepends=True),
                fromfile=f"a/{relative_path}",
                tofile=f"b/{relative_path}",
                lineterm=""
            ))

            # 计算相似度
            similarity = difflib.SequenceMatcher(None, old_text, new_text).ratio()

            return DiffResult(
                file_path=relative_path,
                file_type='text',
                old_size=len(old_text.encode()) if old_text else 0,
                new_size=len(new_text.encode()),
                old_hash=hashlib.sha256(old_text.encode()).hexdigest() if old_text else "",
                new_hash=new_hash,
                diff_lines=diff_lines,
                similarity=similarity
            )

    def _calculate_binary_similarity(self, content1: Optional[bytes], content2: bytes) -> float:
        """计算二进制文件的相似度"""
        if not content1:
            return 0.0

        # 简单的字节级别相似度计算
        if len(content1) == 0 and len(content2) == 0:
            return 1.0

        min_len = min(len(content1), len(content2))
        if min_len == 0:
            return 0.0

        # 计算相同字节的数量
        same_bytes = sum(1 for i in range(min_len) if content1[i] == content2[i])
        return same_bytes / max(len(content1), len(content2))