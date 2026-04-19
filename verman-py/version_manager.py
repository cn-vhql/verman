"""
Core version management logic.
"""

import logging
import threading
import time
from typing import Dict, List, Optional, Tuple

from database import DatabaseManager
from file_manager import FileManager


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


class VersionManager:
    """Business logic for create, compare, rollback, export, and query."""

    def __init__(self, db_manager: DatabaseManager, file_manager: FileManager, config_manager=None):
        self.db_manager = db_manager
        self.file_manager = file_manager
        self.config_manager = config_manager
        self._operation_lock = threading.Lock()
        self._last_scan_cache = None
        self._last_scan_time = 0.0
        self._cache_ttl = 1.0

    def _get_ignore_patterns(self) -> List[str]:
        if self.config_manager:
            try:
                return self.config_manager.get_ignore_patterns()
            except Exception as e:
                _logger.warning(f"获取忽略模式失败: {e}")
        return []

    def _collect_version_context(self) -> Tuple[Dict[str, str], Dict[str, str], List[Dict]]:
        ignore_patterns = self._get_ignore_patterns()
        current_files = self.file_manager.scan_workspace(ignore_patterns)

        previous_files: Dict[str, str] = {}
        latest_version_id = self.db_manager.get_latest_version_id()
        if latest_version_id is not None:
            latest_files = self.db_manager.get_version_files(latest_version_id)
            previous_files = {
                file["relative_path"]: file["file_hash"]
                for file in latest_files
                if file["file_status"] in ["add", "modify", "unmodified"]
            }

        changes = self._detect_changes_accurate(current_files, previous_files)
        return current_files, previous_files, changes

    def get_current_changes(self) -> List[Dict]:
        try:
            current_files = self._get_current_files_with_cache()
            latest_version_id = self.db_manager.get_latest_version_id()

            if latest_version_id is None:
                return [
                    {
                        "relative_path": path,
                        "file_hash": hash_val,
                        "file_status": "add",
                    }
                    for path, hash_val in current_files.items()
                ]

            latest_files = self.db_manager.get_version_files(latest_version_id)
            previous_files = {
                file["relative_path"]: file["file_hash"]
                for file in latest_files
                if file["file_status"] in ["add", "modify", "unmodified"]
            }
            return self._detect_changes_accurate(current_files, previous_files)
        except Exception as e:
            _logger.error(f"获取变更失败: {e}")
            return []

    def _detect_changes_accurate(
        self, current_files: Dict[str, str], previous_files: Dict[str, str]
    ) -> List[Dict]:
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
            changes.append(
                {
                    "relative_path": file_path,
                    "file_hash": previous_files.get(file_path, ""),
                    "file_status": "delete",
                }
            )

        return changes

    def _get_current_files_with_cache(self) -> Dict[str, str]:
        with self._operation_lock:
            current_time = time.time()
            if (
                self._last_scan_cache is not None
                and current_time - self._last_scan_time < self._cache_ttl
            ):
                return self._last_scan_cache

            try:
                ignore_patterns = self._get_ignore_patterns()
                self._last_scan_cache = self.file_manager.scan_workspace(ignore_patterns)
                self._last_scan_time = current_time
                return self._last_scan_cache
            except Exception as e:
                _logger.error(f"扫描工作区失败: {e}")
                self._last_scan_cache = {}
                self._last_scan_time = current_time
                return {}

    def create_version(self, description: str) -> Optional[str]:
        try:
            with self._operation_lock:
                _logger.info("开始创建版本...")
                current_files, previous_files, changes = self._collect_version_context()
                if not changes:
                    _logger.info("没有检测到文件变更，跳过版本创建")
                    return None

                version_number = self._generate_version_number()
                version_files = self._prepare_version_files_fast(current_files, previous_files, changes)

                version_id = self.db_manager.create_version(
                    version_number=version_number,
                    description=description,
                    change_count=len(changes),
                )
                self._save_files_in_batches(version_id, version_files)
                self._clear_scan_cache()
                if hasattr(self.file_manager, "clear_hash_cache"):
                    self.file_manager.clear_hash_cache()

                _logger.info(f"版本 {version_number} 创建成功，包含 {len(changes)} 个变更")
                return version_number
        except Exception as e:
            _logger.error(f"创建版本失败: {e}")
            return None

    def _get_current_changes_fast(self) -> List[Dict]:
        try:
            _, _, changes = self._collect_version_context()
            return changes
        except Exception as e:
            _logger.error(f"快速获取变更失败: {e}")
            return []

    def _prepare_version_files_fast(
        self,
        current_files: Dict[str, str],
        previous_files: Dict[str, str],
        changes: List[Dict],
    ) -> List[Dict]:
        file_status_map = {}

        for change in changes:
            file_status_map[change["relative_path"]] = {
                "status": change["file_status"],
                "hash": change["file_hash"],
            }

        for file_path, file_hash in current_files.items():
            if file_path not in file_status_map:
                if file_path in previous_files and previous_files[file_path] == file_hash:
                    file_status_map[file_path] = {"status": "unmodified", "hash": file_hash}
                else:
                    file_status_map[file_path] = {"status": "add", "hash": file_hash}

        version_files = []
        for file_path in sorted(file_status_map.keys()):
            file_info = file_status_map[file_path]
            status = file_info["status"]
            file_hash = file_info["hash"]
            file_data = {
                "relative_path": file_path,
                "file_hash": file_hash,
                "file_status": status,
                "file_content": None,
            }

            if status in ["add", "modify"]:
                try:
                    full_path = self.file_manager.workspace_path + "\\" + file_path.replace("/", "\\")
                    file_data["file_content"] = self.file_manager._read_file_content(full_path)
                except Exception as e:
                    _logger.warning(f"读取文件内容失败 {file_path}: {e}")
                    file_data["file_status"] = "delete"
                    file_data["file_content"] = None

            version_files.append(file_data)

        return version_files

    def _save_files_in_batches(self, version_id: int, version_files: List[Dict]):
        try:
            batch_size = 100
            for i in range(0, len(version_files), batch_size):
                batch = version_files[i : i + batch_size]
                self.db_manager.save_files(version_id, batch, replace_existing=(i == 0))
        except Exception as e:
            _logger.error(f"分批保存文件失败: {e}")
            raise

    def _get_effective_version_files(self, version_id: int) -> List[Dict]:
        return self.db_manager.get_effective_version_files(version_id)

    def rollback_to_version(self, version_id: int, backup_current: bool = True) -> bool:
        with self._operation_lock:
            try:
                version_files = self._get_effective_version_files(version_id)
                if not version_files:
                    _logger.error("版本文件不存在")
                    return False

                if backup_current:
                    try:
                        self.file_manager._backup_current_state()
                    except Exception as backup_error:
                        _logger.warning(f"备份当前状态失败: {backup_error}")

                success = self.file_manager.restore_files(version_files, False)
                if not success:
                    _logger.error("文件恢复失败")
                    return False

                if not self._verify_rollback_result(version_files):
                    _logger.error("回滚结果验证失败")
                    return False

                self._sync_internal_state_after_rollback(version_id)
                _logger.info(f"成功回滚到版本 {version_id}")
                return True
            except Exception as e:
                _logger.error(f"回滚失败: {e}")
                return False

    def _clear_scan_cache(self):
        self._last_scan_cache = None
        self._last_scan_time = 0
        if hasattr(self.file_manager, "clear_hash_cache"):
            self.file_manager.clear_hash_cache()

    def _verify_rollback_result(self, expected_files: List[Dict]) -> bool:
        try:
            ignore_patterns = self._get_ignore_patterns()
            current_files = self.file_manager.scan_workspace(ignore_patterns)

            expected_file_map = {
                f["relative_path"]: f
                for f in expected_files
                if f["file_status"] in ["add", "modify", "unmodified"]
            }

            mismatches = []
            for file_path, file_info in expected_file_map.items():
                if file_path not in current_files:
                    mismatches.append(f"文件 {file_path} 未找到")
                    continue

                current_hash = current_files[file_path]
                expected_hash = file_info["file_hash"]
                if current_hash != expected_hash:
                    mismatches.append(
                        f"文件 {file_path} 哈希值不匹配: 期望 {expected_hash[:8]}, 实际 {current_hash[:8]}"
                    )

            expected_paths = set(expected_file_map.keys())
            current_paths = set(current_files.keys())
            extra_files = [f for f in current_paths - expected_paths if not f.startswith(".verman")]
            if extra_files:
                mismatches.extend([f"额外文件 {f}" for f in extra_files[:10]])

            if mismatches:
                _logger.warning(f"回滚验证发现 {len(mismatches)} 个问题: {'; '.join(mismatches)}")
                return False

            return True
        except Exception as e:
            _logger.warning(f"验证回滚结果时出错: {e}")
            return False

    def _sync_internal_state_after_rollback(self, target_version_id: int):
        try:
            self._clear_scan_cache()
            versions = self.db_manager.get_all_versions()
            target_exists = any(v["id"] == target_version_id for v in versions)
            if not target_exists:
                _logger.warning(f"目标版本 {target_version_id} 在数据库中不存在")
        except Exception as e:
            _logger.warning(f"同步内部状态时出错: {e}")

    def get_all_versions(self) -> List[Dict]:
        try:
            return self.db_manager.get_all_versions()
        except Exception as e:
            print(f"获取版本列表失败: {e}")
            return []

    def get_version_details(self, version_id: int) -> Optional[Dict]:
        try:
            versions = self.db_manager.get_all_versions()
            version_info = None
            for version in versions:
                if version["id"] == version_id:
                    version_info = version
                    break

            if not version_info:
                return None

            files = self._get_effective_version_files(version_id)
            add_count = len([f for f in files if f["file_status"] == "add"])
            modify_count = len([f for f in files if f["file_status"] == "modify"])
            delete_count = len([f for f in files if f["file_status"] == "delete"])
            unmodified_count = len([f for f in files if f["file_status"] == "unmodified"])

            version_info["files"] = files
            version_info["statistics"] = {
                "add_count": add_count,
                "modify_count": modify_count,
                "delete_count": delete_count,
                "unmodified_count": unmodified_count,
                "total_count": len(files),
            }
            return version_info
        except Exception as e:
            print(f"获取版本详情失败: {e}")
            return None

    def compare_versions(self, version_id1: int, version_id2: int) -> Dict:
        try:
            files1 = self._get_effective_version_files(version_id1)
            files2 = self._get_effective_version_files(version_id2)
            return self._compare_versions_effective(files1, files2)
        except Exception as e:
            _logger.error(f"版本比较失败: {e}")
            return {}

    def _compare_versions_effective(self, files1: List[Dict], files2: List[Dict]) -> Dict:
        differences = {"only_in_first": [], "only_in_second": [], "different": []}

        files1_map = {
            file_info["relative_path"]: file_info
            for file_info in files1
            if file_info["file_status"] != "delete"
        }
        files2_map = {
            file_info["relative_path"]: file_info
            for file_info in files2
            if file_info["file_status"] != "delete"
        }

        paths1 = set(files1_map.keys())
        paths2 = set(files2_map.keys())

        for path in sorted(paths1 - paths2):
            differences["only_in_first"].append(files1_map[path])

        for path in sorted(paths2 - paths1):
            differences["only_in_second"].append(files2_map[path])

        for path in sorted(paths1 & paths2):
            file1 = files1_map[path]
            file2 = files2_map[path]
            if (
                file1["file_hash"] != file2["file_hash"]
                or file1["file_status"] != file2["file_status"]
            ):
                differences["different"].append(
                    {
                        "relative_path": path,
                        "file_in_v1": {
                            "file_hash": file1["file_hash"],
                            "file_status": file1["file_status"],
                        },
                        "file_in_v2": {
                            "file_hash": file2["file_hash"],
                            "file_status": file2["file_status"],
                        },
                    }
                )

        return differences

    def export_version(self, version_id: int, export_path: str) -> bool:
        try:
            version_files = self._get_effective_version_files(version_id)
            if not version_files:
                print("版本文件不存在")
                return False

            success = self.file_manager.export_version_files(version_files, export_path)
            if success:
                print(f"版本已导出到: {export_path}")
            return success
        except Exception as e:
            print(f"导出版本失败: {e}")
            return False

    def delete_version(self, version_id: int) -> bool:
        try:
            self.db_manager.delete_version(version_id)
            print(f"版本 {version_id} 已删除")
            return True
        except Exception as e:
            print(f"删除版本失败: {e}")
            return False

    def _generate_version_number(self) -> str:
        try:
            versions = self.db_manager.get_all_versions()
            if not versions:
                return "v1.0"

            latest_version = versions[0]["version_number"]
            if latest_version.startswith("v"):
                try:
                    parts = latest_version[1:].split(".")
                    if len(parts) == 2:
                        major = int(parts[0])
                        minor = int(parts[1]) + 1
                        new_version = f"v{major}.{minor}"
                        existing_versions = [v["version_number"] for v in versions]
                        if new_version not in existing_versions:
                            return new_version
                except ValueError:
                    pass

            base_time = time.strftime("%Y%m%d_%H%M%S")
            new_version = f"v{base_time}"
            existing_versions = [v["version_number"] for v in versions]
            counter = 1
            while new_version in existing_versions:
                new_version = f"v{base_time}_{counter}"
                counter += 1
            return new_version
        except Exception:
            return f"v{int(time.time())}"
