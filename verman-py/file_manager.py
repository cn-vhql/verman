"""
File scanning, hashing, backup, restore, and export helpers.
"""

import fnmatch
import hashlib
import logging
import os
import shutil
import tempfile
from datetime import datetime
from typing import Dict, List


class _SimpleLogger:
    """Minimal logger wrapper used across the project."""

    def __init__(self):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def info(self, msg):
        self.logger.info(msg)

    def error(self, msg):
        self.logger.error(msg)

    def warning(self, msg):
        self.logger.warning(msg)

    def debug(self, msg):
        self.logger.debug(msg)


_logger = _SimpleLogger()


class FileManager:
    """File operations for the managed workspace."""

    def __init__(self, workspace_path: str):
        self.workspace_path = os.path.abspath(workspace_path)
        self._hash_cache = {}
        self._cache_max_size = 1000
        self._cache_ttl = 300

    def _calculate_file_hash(self, file_path: str, force_recalculate: bool = False) -> str:
        import time

        try:
            relative_path = os.path.relpath(file_path, self.workspace_path)
            if not force_recalculate:
                cached_result = self._get_cached_hash(relative_path, file_path)
                if cached_result is not None:
                    return cached_result

            hash_md5 = hashlib.md5()
            file_size = os.path.getsize(file_path)

            with open(file_path, "rb") as f:
                if file_size == 0:
                    hash_md5.update(b"")
                elif file_size < 10 * 1024 * 1024:
                    for chunk in iter(lambda: f.read(4096), b""):
                        hash_md5.update(chunk)
                else:
                    while True:
                        chunk = f.read(64 * 1024)
                        if not chunk:
                            break
                        hash_md5.update(chunk)

            calculated_hash = hash_md5.hexdigest()
            self._update_hash_cache(relative_path, calculated_hash, file_path)
            return calculated_hash
        except (IOError, OSError):
            return ""

    def _get_cached_hash(self, relative_path: str, file_path: str):
        try:
            if relative_path not in self._hash_cache:
                return None

            cached_hash, cached_time = self._hash_cache[relative_path]
            import time

            current_time = time.time()
            if current_time - cached_time > self._cache_ttl:
                del self._hash_cache[relative_path]
                return None

            file_mtime = os.path.getmtime(file_path)
            if file_mtime > cached_time:
                del self._hash_cache[relative_path]
                return None

            return cached_hash
        except (OSError, KeyError):
            self._hash_cache.pop(relative_path, None)
            return None

    def _update_hash_cache(self, relative_path: str, file_hash: str, file_path: str):
        try:
            import time

            if len(self._hash_cache) >= self._cache_max_size:
                self._cleanup_hash_cache()

            current_time = time.time()
            self._hash_cache[relative_path] = (file_hash, current_time)
        except Exception as e:
            _logger.debug(f"更新哈希缓存失败 {relative_path}: {e}")

    def _cleanup_hash_cache(self):
        try:
            if not self._hash_cache:
                return

            sorted_items = sorted(self._hash_cache.items(), key=lambda x: x[1][1])
            keep_count = int(len(sorted_items) * 0.75)
            self._hash_cache = dict(sorted_items[keep_count:])
        except Exception as e:
            _logger.debug(f"清理哈希缓存失败: {e}")
            self._hash_cache.clear()

    def clear_hash_cache(self):
        self._hash_cache.clear()

    def _read_file_content(self, file_path: str) -> bytes:
        try:
            file_size = os.path.getsize(file_path)
            max_size = 50 * 1024 * 1024
            if file_size > max_size:
                raise ValueError(
                    f"文件过大 ({file_size // 1024 // 1024}MB)，超过限制 ({max_size // 1024 // 1024}MB)"
                )

            if file_size < 10 * 1024 * 1024:
                with open(file_path, "rb") as f:
                    return f.read()

            content = bytearray()
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(4096)
                    if not chunk:
                        break
                    content.extend(chunk)
                    if len(content) > max_size:
                        raise ValueError("文件内容过大，超过内存限制")
            return bytes(content)
        except (IOError, OSError, ValueError) as e:
            _logger.error(f"读取文件失败 {file_path}: {e}")
            return b""

    def scan_workspace(self, ignore_patterns: List[str] = None) -> Dict[str, str]:
        if ignore_patterns is None:
            ignore_patterns = []

        file_hashes: Dict[str, str] = {}
        default_ignore = [
            ".verman.db",
            "*.db",
            "*.sqlite",
            "*.sqlite3",
            ".verman_backup",
            ".verman_temp",
            "__pycache__",
            "*.pyc",
            "*.pyo",
            ".git",
            ".svn",
            ".hg",
            "*.tmp",
            "*.temp",
            "*.log",
            ".DS_Store",
            "Thumbs.db",
        ]
        all_ignore_patterns = default_ignore + self._load_ignore_file() + ignore_patterns

        if not os.path.exists(self.workspace_path):
            raise FileNotFoundError(f"工作区路径不存在: {self.workspace_path}")
        if not os.access(self.workspace_path, os.R_OK):
            raise PermissionError(f"工作区路径不可读: {self.workspace_path}")

        file_count = 0
        max_files = 10000

        for root, dirs, files in os.walk(self.workspace_path):
            try:
                relative_root = os.path.relpath(root, self.workspace_path)
                if relative_root.startswith(".."):
                    continue
            except ValueError:
                continue

            filtered_dirs = []
            for dir_name in dirs:
                dir_relative = os.path.relpath(os.path.join(root, dir_name), self.workspace_path)
                if not self._should_ignore(dir_relative, all_ignore_patterns, is_dir=True):
                    filtered_dirs.append(dir_name)
            dirs[:] = filtered_dirs

            for file_name in files:
                if file_count >= max_files:
                    _logger.warning(f"文件数量超过限制 ({max_files})，停止扫描")
                    return file_hashes

                file_path = os.path.join(root, file_name)
                if os.path.islink(file_path):
                    try:
                        link_target = os.path.realpath(file_path)
                        target_relative = os.path.relpath(link_target, self.workspace_path)
                        if target_relative.startswith(".."):
                            _logger.debug(f"跳过外部链接 {file_path} -> {link_target}")
                            continue
                        file_path = link_target
                    except (OSError, ValueError):
                        _logger.debug(f"跳过无效链接 {file_path}")
                        continue

                try:
                    relative_path = os.path.relpath(file_path, self.workspace_path)
                    if (
                        relative_path.startswith("..")
                        or ".." in relative_path.split(os.sep)
                        or os.path.isabs(relative_path)
                    ):
                        continue
                except ValueError:
                    continue

                if self._should_ignore(relative_path, all_ignore_patterns, is_dir=False):
                    continue

                try:
                    if not os.access(file_path, os.R_OK):
                        continue

                    file_size = os.path.getsize(file_path)
                    if file_size > 100 * 1024 * 1024:
                        _logger.warning(
                            f"跳过过大文件 {relative_path} ({file_size // 1024 // 1024}MB)"
                        )
                        continue

                    file_hash = self._calculate_file_hash(file_path)
                    if file_hash:
                        file_hashes[relative_path] = file_hash
                        file_count += 1
                except (OSError, IOError, ValueError) as e:
                    _logger.warning(f"跳过文件 {relative_path}: {e}")
                    continue

        return file_hashes

    def _load_ignore_file(self) -> List[str]:
        ignore_file_path = os.path.join(self.workspace_path, ".vermanignore")
        patterns = []
        try:
            if os.path.exists(ignore_file_path):
                with open(ignore_file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            patterns.append(line)
        except (IOError, OSError, UnicodeDecodeError) as e:
            _logger.warning(f"读取忽略文件失败: {e}")
        return patterns

    def _should_ignore(self, name: str, ignore_patterns: List[str], is_dir: bool = False) -> bool:
        normalized_name = name.replace("\\", "/").strip("./")
        basename = os.path.basename(normalized_name.rstrip("/"))

        for pattern in ignore_patterns:
            normalized_pattern = pattern.replace("\\", "/").strip()
            if not normalized_pattern:
                continue

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

    def detect_changes(self, current_files: Dict[str, str], previous_files: Dict[str, str]) -> List[Dict]:
        changes = []
        current_set = set(current_files.keys())
        previous_set = set(previous_files.keys())

        for file_path in sorted(current_set - previous_set):
            if file_path.startswith(".verman"):
                continue
            changes.append(
                {
                    "relative_path": file_path,
                    "file_hash": current_files[file_path],
                    "file_status": "add",
                }
            )

        for file_path in sorted(current_set & previous_set):
            if current_files[file_path] != previous_files[file_path]:
                changes.append(
                    {
                        "relative_path": file_path,
                        "file_hash": current_files[file_path],
                        "file_status": "modify",
                    }
                )

        for file_path in sorted(previous_set - current_set):
            if file_path.startswith(".verman"):
                continue
            if self._confirm_file_deletion(file_path, previous_files.get(file_path, "")):
                changes.append(
                    {
                        "relative_path": file_path,
                        "file_hash": previous_files.get(file_path, ""),
                        "file_status": "delete",
                    }
                )
            else:
                _logger.info(f"文件 {file_path} 可能被临时移动，暂不记录为删除")

        return changes

    def _confirm_file_deletion(self, file_path: str, original_hash: str) -> bool:
        try:
            full_path = os.path.join(self.workspace_path, file_path)
            if os.path.exists(full_path):
                return False
            if self._is_file_temporarily_moved(file_path, original_hash):
                return False
            return True
        except Exception as e:
            _logger.warning(f"确认文件删除状态时出错 {file_path}: {e}")
            return True

    def _is_file_temporarily_moved(self, file_path: str, original_hash: str) -> bool:
        if not original_hash:
            return False

        try:
            temp_locations = [
                ".verman_backup",
                ".verman_temp",
                "temp",
                "tmp",
                os.path.expanduser("~/.Trash"),
                os.path.expanduser("~/Desktop"),
            ]

            for temp_dir in temp_locations:
                temp_path = os.path.join(self.workspace_path, temp_dir)
                if os.path.exists(temp_path) and self._search_file_by_hash(temp_path, original_hash, file_path):
                    return True

            system_temp = tempfile.gettempdir()
            return self._search_file_by_hash(system_temp, original_hash, file_path)
        except Exception as e:
            _logger.debug(f"检查文件临时移动时出错 {file_path}: {e}")
            return False

    def _search_file_by_hash(self, search_path: str, target_hash: str, original_name: str) -> bool:
        try:
            if not os.path.exists(search_path):
                return False

            max_depth = 3
            max_files = 100
            searched_files = 0

            for root, dirs, files in os.walk(search_path):
                current_depth = os.path.relpath(root, search_path).count(os.sep) + 1
                if current_depth > max_depth:
                    continue

                for file_name in files:
                    if searched_files >= max_files:
                        return False
                    searched_files += 1

                    if file_name == os.path.basename(original_name) or searched_files < 50:
                        file_path = os.path.join(root, file_name)
                        try:
                            file_hash = self._calculate_file_hash(file_path)
                            if file_hash == target_hash:
                                return True
                        except Exception:
                            continue
            return False
        except Exception:
            return False

    def prepare_files_for_version(self, changes: List[Dict]) -> List[Dict]:
        version_files = []
        for change in changes:
            file_data = {
                "relative_path": change["relative_path"],
                "file_hash": change["file_hash"],
                "file_status": change["file_status"],
            }
            if change["file_status"] in ["add", "modify"]:
                file_path = os.path.join(self.workspace_path, change["relative_path"])
                file_data["file_content"] = self._read_file_content(file_path)
            else:
                file_data["file_content"] = None
            version_files.append(file_data)
        return version_files

    def restore_files(self, version_files: List[Dict], backup_current: bool = True) -> bool:
        try:
            if backup_current:
                self._backup_current_state()

            for file_data in version_files:
                relative_path = file_data["relative_path"]
                file_status = file_data["file_status"]
                file_content = file_data.get("file_content")
                target_path = os.path.join(self.workspace_path, relative_path)

                os.makedirs(os.path.dirname(target_path), exist_ok=True)

                if file_status == "delete":
                    if os.path.exists(target_path):
                        os.remove(target_path)
                elif file_status in ["add", "modify", "unmodified"] and file_content is not None:
                    with open(target_path, "wb") as f:
                        f.write(file_content)

            return True
        except Exception as e:
            _logger.error(f"文件恢复失败: {e}")
            return False

    def _backup_current_state(self):
        backup_dir = os.path.join(self.workspace_path, ".verman_backup")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"backup_{timestamp}")

        try:
            os.makedirs(backup_path, exist_ok=True)
            current_files = self.scan_workspace()
            backed_up_count = 0

            for relative_path in current_files:
                source_path = os.path.join(self.workspace_path, relative_path)
                target_path = os.path.join(backup_path, relative_path)
                target_dir = os.path.dirname(target_path)
                if target_dir:
                    os.makedirs(target_dir, exist_ok=True)

                try:
                    shutil.copy2(source_path, target_path)
                    backed_up_count += 1
                except Exception as copy_error:
                    _logger.error(f"备份文件失败 {relative_path}: {copy_error}")

            _logger.info(f"当前状态已备份到: {backup_path}")
            _logger.info(f"共备份 {backed_up_count} 个文件")
        except Exception as e:
            _logger.error(f"备份失败: {e}")

    def export_version_files(self, version_files: List[Dict], export_path: str) -> bool:
        try:
            for file_data in version_files:
                if file_data["file_status"] == "delete":
                    continue

                relative_path = file_data["relative_path"]
                file_content = file_data.get("file_content")
                if file_content is None:
                    continue

                target_path = os.path.join(export_path, relative_path)
                os.makedirs(os.path.dirname(target_path), exist_ok=True)

                with open(target_path, "wb") as f:
                    f.write(file_content)

            return True
        except Exception as e:
            _logger.error(f"导出失败: {e}")
            return False
