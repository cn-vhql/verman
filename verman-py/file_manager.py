"""
File scanning, hashing, backup, restore, and export helpers.
"""

import fnmatch
import hashlib
import os
import shutil
import tempfile
import time
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

from logger import logger as app_logger
from models import (
    ACTIVE_FILE_STATUSES,
    DEFAULT_IGNORE_PATTERNS,
    BlockedFile,
    FileState,
)
from project_paths import get_backup_dir, get_ignore_file_path


class FileManager:
    """File operations for the managed workspace."""

    def __init__(self, workspace_path: str):
        self.workspace_path = os.path.abspath(workspace_path)
        self._hash_cache: Dict[str, Tuple[str, int, int, float]] = {}
        self._cache_max_size = 1000
        self._cache_ttl = 300.0

    def clear_hash_cache(self):
        self._hash_cache.clear()

    def scan_workspace(
        self,
        ignore_patterns: Optional[List[str]] = None,
        indexed_files: Optional[Dict[str, Dict[str, int]]] = None,
    ) -> Tuple[Dict[str, FileState], List[BlockedFile]]:
        """
        Scan the workspace and reuse stored hashes when size and mtime match.
        """
        indexed_files = indexed_files or {}
        current_files: Dict[str, FileState] = {}
        blocked_files: List[BlockedFile] = []

        for relative_path, file_path in self._iter_visible_files(ignore_patterns):
            try:
                stat_result = os.stat(file_path)
                file_size = stat_result.st_size
                mtime_ns = stat_result.st_mtime_ns
            except OSError as exc:
                app_logger.warning(f"跳过文件 {relative_path}: {exc}")
                continue

            indexed_state = indexed_files.get(relative_path)
            if (
                indexed_state
                and indexed_state.get("file_size") == file_size
                and indexed_state.get("mtime_ns") == mtime_ns
                and indexed_state.get("file_hash")
            ):
                file_hash = indexed_state["file_hash"]
            else:
                file_hash = self._calculate_file_hash(file_path, file_size, mtime_ns)

            if not file_hash:
                continue

            current_files[relative_path] = FileState(
                relative_path=relative_path,
                file_hash=file_hash,
                file_size=file_size,
                mtime_ns=mtime_ns,
            )

        return current_files, blocked_files

    def list_workspace_files(self, ignore_patterns: Optional[List[str]] = None) -> List[str]:
        return [
            relative_path
            for relative_path, _ in self._iter_visible_files(ignore_patterns)
        ]

    def read_relative_file(self, relative_path: str) -> bytes:
        full_path = os.path.join(self.workspace_path, relative_path)
        return self._read_file_content(full_path)

    def restore_files(
        self,
        version_files: List[Dict],
        ignore_patterns: Optional[List[str]] = None,
        backup_current: bool = True,
    ) -> Dict[str, object]:
        try:
            if backup_current:
                self._backup_current_state(ignore_patterns)

            desired_active = {
                file_info["relative_path"]: file_info
                for file_info in version_files
                if file_info["file_status"] in ACTIVE_FILE_STATUSES
            }
            desired_paths = set(desired_active.keys())
            current_paths = set(self.list_workspace_files(ignore_patterns))

            restored_count = 0
            removed_count = 0
            warnings: List[str] = []

            for extra_path in sorted(current_paths - desired_paths):
                full_path = os.path.join(self.workspace_path, extra_path)
                if os.path.exists(full_path):
                    os.remove(full_path)
                    removed_count += 1
                    self._cleanup_empty_directories(os.path.dirname(full_path))

            for file_data in version_files:
                relative_path = file_data["relative_path"]
                file_status = file_data["file_status"]
                target_path = os.path.join(self.workspace_path, relative_path)

                if file_status == "delete":
                    if os.path.exists(target_path):
                        os.remove(target_path)
                        removed_count += 1
                        self._cleanup_empty_directories(os.path.dirname(target_path))
                    continue

                file_content = file_data.get("file_content")
                if file_content is None:
                    raise ValueError(f"版本文件缺少内容: {relative_path}")

                target_dir = os.path.dirname(target_path)
                if target_dir:
                    os.makedirs(target_dir, exist_ok=True)
                with open(target_path, "wb") as file_handle:
                    file_handle.write(file_content)
                restored_count += 1

            return {
                "restored_count": restored_count,
                "removed_count": removed_count,
                "warnings": warnings,
            }
        except Exception as exc:
            app_logger.error(f"文件恢复失败: {exc}")
            raise

    def export_version_files(self, version_files: List[Dict], export_path: str) -> bool:
        try:
            for file_data in version_files:
                if file_data["file_status"] == "delete":
                    continue

                relative_path = file_data["relative_path"]
                file_content = file_data.get("file_content")
                if file_content is None:
                    raise ValueError(f"导出文件缺少内容: {relative_path}")

                target_path = os.path.join(export_path, relative_path)
                target_dir = os.path.dirname(target_path)
                if target_dir:
                    os.makedirs(target_dir, exist_ok=True)
                with open(target_path, "wb") as file_handle:
                    file_handle.write(file_content)

            return True
        except Exception as exc:
            app_logger.error(f"导出失败: {exc}")
            return False

    def _iter_visible_files(self, ignore_patterns: Optional[List[str]]) -> Iterable[Tuple[str, str]]:
        all_ignore_patterns = list(DEFAULT_IGNORE_PATTERNS)
        all_ignore_patterns.extend(self._load_ignore_file())
        all_ignore_patterns.extend(ignore_patterns or [])

        if not os.path.exists(self.workspace_path):
            raise FileNotFoundError(f"工作区路径不存在: {self.workspace_path}")
        if not os.access(self.workspace_path, os.R_OK):
            raise PermissionError(f"工作区路径不可读: {self.workspace_path}")

        max_files = 10000
        yielded = 0

        for root, dirs, files in os.walk(self.workspace_path):
            relative_root = os.path.relpath(root, self.workspace_path)
            if relative_root.startswith(".."):
                continue

            dirs[:] = [
                dir_name
                for dir_name in dirs
                if not self._should_ignore(
                    os.path.relpath(os.path.join(root, dir_name), self.workspace_path),
                    all_ignore_patterns,
                    is_dir=True,
                )
            ]

            for file_name in files:
                file_path = os.path.join(root, file_name)
                file_path = self._resolve_symlink_path(file_path)
                if file_path is None:
                    continue

                relative_path = os.path.relpath(file_path, self.workspace_path)
                if (
                    relative_path.startswith("..")
                    or ".." in relative_path.split(os.sep)
                    or os.path.isabs(relative_path)
                ):
                    continue

                if self._should_ignore(relative_path, all_ignore_patterns, is_dir=False):
                    continue

                if not os.access(file_path, os.R_OK):
                    continue

                yielded += 1
                if yielded > max_files:
                    app_logger.warning(f"文件数量超过限制 ({max_files})，停止扫描")
                    return

                yield relative_path.replace("\\", "/"), file_path

    def _resolve_symlink_path(self, file_path: str) -> Optional[str]:
        if not os.path.islink(file_path):
            return file_path

        try:
            link_target = os.path.realpath(file_path)
            target_relative = os.path.relpath(link_target, self.workspace_path)
            if target_relative.startswith(".."):
                app_logger.debug(f"跳过外部链接 {file_path} -> {link_target}")
                return None
            return link_target
        except (OSError, ValueError):
            app_logger.debug(f"跳过无效链接 {file_path}")
            return None

    def _calculate_file_hash(self, file_path: str, file_size: int, mtime_ns: int) -> str:
        relative_path = os.path.relpath(file_path, self.workspace_path).replace("\\", "/")
        cached_result = self._get_cached_hash(relative_path, file_size, mtime_ns)
        if cached_result is not None:
            return cached_result

        try:
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as file_handle:
                chunk_size = 4096 if file_size < 10 * 1024 * 1024 else 64 * 1024
                for chunk in iter(lambda: file_handle.read(chunk_size), b""):
                    hash_md5.update(chunk)

            calculated_hash = hash_md5.hexdigest()
            self._update_hash_cache(relative_path, calculated_hash, file_size, mtime_ns)
            return calculated_hash
        except (IOError, OSError) as exc:
            app_logger.warning(f"计算文件哈希失败 {file_path}: {exc}")
            return ""

    def _get_cached_hash(
        self, relative_path: str, file_size: int, mtime_ns: int
    ) -> Optional[str]:
        cached_entry = self._hash_cache.get(relative_path)
        if not cached_entry:
            return None

        cached_hash, cached_size, cached_mtime_ns, cached_at = cached_entry
        if time.time() - cached_at > self._cache_ttl:
            self._hash_cache.pop(relative_path, None)
            return None

        if cached_size != file_size or cached_mtime_ns != mtime_ns:
            self._hash_cache.pop(relative_path, None)
            return None

        return cached_hash

    def _update_hash_cache(self, relative_path: str, file_hash: str, file_size: int, mtime_ns: int):
        if len(self._hash_cache) >= self._cache_max_size:
            self._cleanup_hash_cache()

        self._hash_cache[relative_path] = (file_hash, file_size, mtime_ns, time.time())

    def _cleanup_hash_cache(self):
        if not self._hash_cache:
            return

        sorted_items = sorted(self._hash_cache.items(), key=lambda item: item[1][3])
        keep_count = int(len(sorted_items) * 0.75)
        self._hash_cache = dict(sorted_items[keep_count:])

    def _read_file_content(self, file_path: str) -> bytes:
        with open(file_path, "rb") as file_handle:
            return file_handle.read()

    def _load_ignore_file(self) -> List[str]:
        ignore_file_path = get_ignore_file_path(self.workspace_path)
        patterns = []
        try:
            if os.path.exists(ignore_file_path):
                with open(ignore_file_path, "r", encoding="utf-8") as file_handle:
                    for line in file_handle:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            patterns.append(line)
        except (IOError, OSError, UnicodeDecodeError) as exc:
            app_logger.warning(f"读取忽略文件失败: {exc}")
        return patterns

    def _should_ignore(self, name: str, ignore_patterns: List[str], is_dir: bool = False) -> bool:
        normalized_name = name.replace("\\", "/").strip()
        if normalized_name.startswith("./"):
            normalized_name = normalized_name[2:]
        normalized_name = normalized_name.strip("/")
        basename = os.path.basename(normalized_name.rstrip("/"))

        for pattern in ignore_patterns:
            normalized_pattern = pattern.replace("\\", "/").strip()
            if not normalized_pattern:
                continue
            if normalized_pattern.startswith("./"):
                normalized_pattern = normalized_pattern[2:]

            if normalized_pattern.endswith("/"):
                if not is_dir:
                    continue
                dir_pattern = normalized_pattern.rstrip("/")
                if (
                    normalized_name == dir_pattern
                    or normalized_name.startswith(dir_pattern + "/")
                    or basename == dir_pattern
                    or fnmatch.fnmatch(normalized_name, dir_pattern)
                    or fnmatch.fnmatch(basename, dir_pattern)
                ):
                    return True
                continue

            if (
                fnmatch.fnmatch(basename, normalized_pattern)
                or fnmatch.fnmatch(normalized_name, normalized_pattern)
            ):
                return True

        return False

    def _backup_current_state(self, ignore_patterns: Optional[List[str]] = None):
        backup_dir = get_backup_dir(self.workspace_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"backup_{timestamp}")

        os.makedirs(backup_path, exist_ok=True)
        backed_up_count = 0

        for relative_path in self.list_workspace_files(ignore_patterns):
            source_path = os.path.join(self.workspace_path, relative_path)
            target_path = os.path.join(backup_path, relative_path)
            target_dir = os.path.dirname(target_path)
            if target_dir:
                os.makedirs(target_dir, exist_ok=True)
            shutil.copy2(source_path, target_path)
            backed_up_count += 1

        app_logger.info(f"当前状态已备份到: {backup_path}")
        app_logger.info(f"共备份 {backed_up_count} 个文件")

    def _cleanup_empty_directories(self, start_dir: str):
        current_dir = start_dir
        workspace_root = os.path.abspath(self.workspace_path)

        while current_dir and os.path.abspath(current_dir).startswith(workspace_root):
            if os.path.abspath(current_dir) == workspace_root:
                break
            try:
                os.rmdir(current_dir)
            except OSError:
                break
            current_dir = os.path.dirname(current_dir)
