"""
Core version management logic.
"""

import threading
import time
from typing import Dict, List, Optional, Tuple

from database import DatabaseManager
from file_manager import FileManager
from logger import logger as app_logger
from models import (
    ACTIVE_FILE_STATUSES,
    CreateVersionResult,
    RollbackResult,
    ScanSnapshot,
)


class VersionManager:
    """Business logic for create, compare, rollback, export, and query."""

    def __init__(self, db_manager: DatabaseManager, file_manager: FileManager, config_manager=None):
        self.db_manager = db_manager
        self.file_manager = file_manager
        self.config_manager = config_manager
        self._operation_lock = threading.RLock()
        self._last_scan_snapshot: Optional[ScanSnapshot] = None
        self._last_scan_time = 0.0
        self._cache_ttl = 1.0

    def _get_ignore_patterns(self) -> List[str]:
        if self.config_manager:
            try:
                return self.config_manager.get_ignore_patterns()
            except Exception as exc:
                app_logger.warning(f"获取忽略模式失败: {exc}")
        return []

    def refresh_workspace(self, force: bool = False) -> ScanSnapshot:
        with self._operation_lock:
            current_time = time.time()
            if (
                not force
                and self._last_scan_snapshot is not None
                and current_time - self._last_scan_time < self._cache_ttl
            ):
                return self._last_scan_snapshot

            ignore_patterns = self._get_ignore_patterns()
            indexed_files = self.db_manager.get_workspace_index()
            current_files, blocked_files = self.file_manager.scan_workspace(ignore_patterns, indexed_files)
            scan_id = time.time_ns()
            self.db_manager.update_workspace_index(current_files.values(), scan_id)

            previous_files = self._get_latest_version_hashes()
            changes = self._detect_changes(
                current_files=current_files,
                previous_files=previous_files,
                blocked_paths={blocked_file.relative_path for blocked_file in blocked_files},
            )

            snapshot = ScanSnapshot(
                current_files=current_files,
                changes=changes,
                blocked_files=blocked_files,
                scan_id=scan_id,
            )
            self._last_scan_snapshot = snapshot
            self._last_scan_time = current_time
            return snapshot

    def get_current_changes(self) -> List[Dict]:
        try:
            return self.refresh_workspace().changes
        except Exception as exc:
            app_logger.error(f"获取变更失败: {exc}")
            return []

    def create_version(
        self,
        description: str,
        scan_snapshot: Optional[ScanSnapshot] = None,
    ) -> CreateVersionResult:
        with self._operation_lock:
            try:
                snapshot = scan_snapshot or self.refresh_workspace(force=True)
                if not snapshot.changes:
                    return CreateVersionResult(success=False, error="没有检测到文件变更。")

                app_logger.info("开始创建版本...")
                previous_files = self._get_latest_version_hashes()
                version_files = self._prepare_version_files(
                    current_files=snapshot.current_files,
                    previous_files=previous_files,
                    changes=snapshot.changes,
                )

                version_number = self._generate_version_number()
                version_id = self.db_manager.create_version(
                    version_number=version_number,
                    description=description,
                    change_count=len(snapshot.changes),
                )
                self._save_files_in_batches(version_id, version_files)
                self._clear_scan_cache()

                app_logger.info(
                    f"版本 {version_number} 创建成功，包含 {len(snapshot.changes)} 个变更"
                )
                return CreateVersionResult(
                    success=True,
                    version_number=version_number,
                    change_count=len(snapshot.changes),
                )
            except Exception as exc:
                app_logger.error(f"创建版本失败: {exc}")
                return CreateVersionResult(success=False, error=str(exc))

    def rollback_to_version(self, version_id: int, backup_current: bool = True) -> RollbackResult:
        with self._operation_lock:
            try:
                version_files = self._get_effective_version_files(version_id)
                if not version_files:
                    return RollbackResult(success=False, error="版本文件不存在。")

                ignore_patterns = self._get_ignore_patterns()
                restore_result = self.file_manager.restore_files(
                    version_files,
                    ignore_patterns=ignore_patterns,
                    backup_current=backup_current,
                )
                is_valid, warnings = self._verify_rollback_result(version_files)
                combined_warnings = restore_result["warnings"] + warnings
                if not is_valid:
                    return RollbackResult(
                        success=False,
                        restored_count=int(restore_result["restored_count"]),
                        removed_count=int(restore_result["removed_count"]),
                        warnings=combined_warnings,
                        error="回滚结果验证失败。",
                    )

                self._clear_scan_cache()
                app_logger.info(f"成功回滚到版本 {version_id}")
                return RollbackResult(
                    success=True,
                    restored_count=int(restore_result["restored_count"]),
                    removed_count=int(restore_result["removed_count"]),
                    warnings=combined_warnings,
                )
            except Exception as exc:
                app_logger.error(f"回滚失败: {exc}")
                return RollbackResult(success=False, error=str(exc))

    def get_all_versions(self) -> List[Dict]:
        try:
            return self.db_manager.get_all_versions()
        except Exception as exc:
            app_logger.error(f"获取版本列表失败: {exc}")
            return []

    def get_version_details(self, version_id: int) -> Optional[Dict]:
        try:
            versions = self.db_manager.get_all_versions()
            version_info = next((version for version in versions if version["id"] == version_id), None)
            if not version_info:
                return None

            files = self._get_effective_version_files(version_id)
            add_count = len([file_info for file_info in files if file_info["file_status"] == "add"])
            modify_count = len(
                [file_info for file_info in files if file_info["file_status"] == "modify"]
            )
            delete_count = len([file_info for file_info in files if file_info["file_status"] == "delete"])
            unmodified_count = len(
                [file_info for file_info in files if file_info["file_status"] == "unmodified"]
            )

            version_info["files"] = files
            version_info["statistics"] = {
                "add_count": add_count,
                "modify_count": modify_count,
                "delete_count": delete_count,
                "unmodified_count": unmodified_count,
                "total_count": len(files),
            }
            return version_info
        except Exception as exc:
            app_logger.error(f"获取版本详情失败: {exc}")
            return None

    def compare_versions(self, version_id1: int, version_id2: int) -> Dict:
        try:
            files1 = self._get_effective_version_files(version_id1, include_content=False)
            files2 = self._get_effective_version_files(version_id2, include_content=False)
            return self._compare_versions_effective(files1, files2)
        except Exception as exc:
            app_logger.error(f"版本比较失败: {exc}")
            return {}

    def export_version(self, version_id: int, export_path: str) -> bool:
        try:
            version_files = self._get_effective_version_files(version_id)
            if not version_files:
                return False

            return self.file_manager.export_version_files(version_files, export_path)
        except Exception as exc:
            app_logger.error(f"导出版本失败: {exc}")
            return False

    def delete_version(self, version_id: int) -> bool:
        try:
            self.db_manager.delete_version(version_id)
            return True
        except Exception as exc:
            app_logger.error(f"删除版本失败: {exc}")
            return False

    def _get_latest_version_hashes(self) -> Dict[str, str]:
        latest_version_id = self.db_manager.get_latest_version_id()
        if latest_version_id is None:
            return {}
        return self.db_manager.get_version_file_hashes(latest_version_id)

    def _detect_changes(
        self,
        current_files: Dict[str, object],
        previous_files: Dict[str, str],
        blocked_paths: Optional[set] = None,
    ) -> List[Dict]:
        blocked_paths = blocked_paths or set()
        changes = []
        current_set = set(current_files.keys())
        previous_set = set(previous_files.keys())

        for file_path in sorted(current_set - previous_set):
            if file_path.startswith(".verman"):
                continue
            changes.append(
                {
                    "relative_path": file_path,
                    "file_hash": current_files[file_path].file_hash,
                    "file_status": "add",
                }
            )

        for file_path in sorted(current_set & previous_set):
            current_hash = current_files[file_path].file_hash
            if current_hash != previous_files[file_path]:
                changes.append(
                    {
                        "relative_path": file_path,
                        "file_hash": current_hash,
                        "file_status": "modify",
                    }
                )

        for file_path in sorted(previous_set - current_set):
            if file_path.startswith(".verman") or file_path in blocked_paths:
                continue
            changes.append(
                {
                    "relative_path": file_path,
                    "file_hash": previous_files.get(file_path, ""),
                    "file_status": "delete",
                }
            )

        return changes

    def _prepare_version_files(
        self,
        current_files: Dict[str, object],
        previous_files: Dict[str, str],
        changes: List[Dict],
    ) -> List[Dict]:
        file_status_map = {}

        for change in changes:
            file_status_map[change["relative_path"]] = {
                "status": change["file_status"],
                "hash": change["file_hash"],
            }

        for file_path, file_state in current_files.items():
            if file_path not in file_status_map:
                if previous_files.get(file_path) == file_state.file_hash:
                    file_status_map[file_path] = {"status": "unmodified", "hash": file_state.file_hash}
                else:
                    file_status_map[file_path] = {"status": "add", "hash": file_state.file_hash}

        version_files = []
        for file_path in sorted(file_status_map.keys()):
            file_info = file_status_map[file_path]
            status = file_info["status"]
            file_data = {
                "relative_path": file_path,
                "file_hash": file_info["hash"],
                "file_status": status,
                "file_content": None,
            }

            if status in {"add", "modify"}:
                file_data["file_content"] = self.file_manager.read_relative_file(file_path)

            version_files.append(file_data)

        return version_files

    def _save_files_in_batches(self, version_id: int, version_files: List[Dict]):
        batch_size = 100
        for index in range(0, len(version_files), batch_size):
            batch = version_files[index : index + batch_size]
            self.db_manager.save_files(version_id, batch, replace_existing=(index == 0))

    def _get_effective_version_files(
        self, version_id: int, include_content: bool = True
    ) -> List[Dict]:
        return self.db_manager.get_effective_version_files(version_id, include_content=include_content)

    def _clear_scan_cache(self):
        self._last_scan_snapshot = None
        self._last_scan_time = 0.0
        self.file_manager.clear_hash_cache()

    def _verify_rollback_result(self, expected_files: List[Dict]) -> Tuple[bool, List[str]]:
        try:
            ignore_patterns = self._get_ignore_patterns()
            current_files, _ = self.file_manager.scan_workspace(ignore_patterns, {})
            current_paths = set(self.file_manager.list_workspace_files(ignore_patterns))

            expected_file_map = {
                file_info["relative_path"]: file_info
                for file_info in expected_files
                if file_info["file_status"] in ACTIVE_FILE_STATUSES
            }

            mismatches = []
            for file_path, file_info in expected_file_map.items():
                current_state = current_files.get(file_path)
                if current_state is None:
                    mismatches.append(f"文件 {file_path} 未找到")
                    continue

                current_hash = current_state.file_hash
                expected_hash = file_info["file_hash"]
                if current_hash != expected_hash:
                    mismatches.append(
                        f"文件 {file_path} 哈希值不匹配: 期望 {expected_hash[:8]}, 实际 {current_hash[:8]}"
                    )

            extra_files = sorted(current_paths - set(expected_file_map.keys()))
            mismatches.extend([f"额外文件 {file_path}" for file_path in extra_files[:10]])

            if mismatches:
                app_logger.warning(f"回滚验证发现 {len(mismatches)} 个问题: {'; '.join(mismatches)}")
                return False, mismatches

            return True, []
        except Exception as exc:
            app_logger.warning(f"验证回滚结果时出错: {exc}")
            return False, [str(exc)]

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

    def _generate_version_number(self) -> str:
        try:
            versions = self.db_manager.get_all_versions()
            if not versions:
                return "v1.0"

            latest_version = versions[0]["version_number"]
            if latest_version.startswith("v"):
                try:
                    major_text, minor_text = latest_version[1:].split(".")
                    new_version = f"v{int(major_text)}.{int(minor_text) + 1}"
                    if new_version not in {version["version_number"] for version in versions}:
                        return new_version
                except ValueError:
                    pass

            base_time = time.strftime("%Y%m%d_%H%M%S")
            candidate = f"v{base_time}"
            existing_versions = {version["version_number"] for version in versions}
            counter = 1
            while candidate in existing_versions:
                candidate = f"v{base_time}_{counter}"
                counter += 1
            return candidate
        except Exception:
            return f"v{int(time.time())}"
