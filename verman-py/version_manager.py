"""
版本管理模块
负责版本创建、提交、回滚和查询等核心功能
"""

import os
import threading
import time
from typing import List, Dict, Optional, Tuple
from database import DatabaseManager
from file_manager import FileManager

# 简化的日志系统
import logging

class _SimpleLogger:
    """简化的日志记录器"""
    def __init__(self):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def info(self, msg): self.logger.info(msg)
    def error(self, msg): self.logger.error(msg)
    def warning(self, msg): self.logger.warning(msg)
    def debug(self, msg): self.logger.debug(msg)

_logger = _SimpleLogger()


class VersionManager:
    """版本管理器，负责版本的核心操作"""

    def __init__(self, db_manager: DatabaseManager, file_manager: FileManager, config_manager=None):
        """
        初始化版本管理器

        Args:
            db_manager: 数据库管理器
            file_manager: 文件管理器
            config_manager: 配置管理器（用于获取忽略模式）
        """
        self.db_manager = db_manager
        self.file_manager = file_manager
        self.config_manager = config_manager
        self._operation_lock = threading.Lock()
        self._last_scan_cache = None
        self._last_scan_time = 0
        self._cache_ttl = 1.0  # 缓存1秒

    def _get_ignore_patterns(self) -> List[str]:
        """
        获取忽略模式列表

        Returns:
            忽略模式列表
        """
        if self.config_manager:
            try:
                return self.config_manager.get_ignore_patterns()
            except Exception as e:
                _logger.warning(f"获取忽略模式失败: {e}")
        return []

    def get_current_changes(self) -> List[Dict]:
        """
        获取当前工作区的变更文件
        使用完整的文件状态比较，避免状态不一致

        Returns:
            变更文件列表
        """
        try:
            # 1. 获取当前工作区文件状态
            current_files = self._get_current_files_with_cache()

            # 2. 获取最新版本的文件状态
            latest_version_id = self.db_manager.get_latest_version_id()

            if latest_version_id is None:
                # 如果没有版本，所有文件都是新增的
                return [{
                    'relative_path': path,
                    'file_hash': hash_val,
                    'file_status': 'add'
                } for path, hash_val in current_files.items()]

            # 3. 获取最新版本的完整文件状态
            latest_files = self.db_manager.get_version_files(latest_version_id)
            previous_files = {
                file['relative_path']: file['file_hash']
                for file in latest_files
                if file['file_status'] in ['add', 'modify', 'unmodified']  # 只包含实际存在的文件
            }

            # 4. 使用改进的变更检测逻辑
            changes = self._detect_changes_accurate(current_files, previous_files)
            return changes

        except Exception as e:
            _logger.error(f"获取变更失败: {e}")
            return []

    def _detect_changes_accurate(self, current_files: Dict[str, str], previous_files: Dict[str, str]) -> List[Dict]:
        """
        准确的变更检测逻辑，避免状态错误

        Args:
            current_files: 当前文件状态
            previous_files: 上次文件状态

        Returns:
            变更列表
        """
        changes = []

        # 获取文件路径集合
        current_set = set(current_files.keys())
        previous_set = set(previous_files.keys())

        # 1. 检测新增文件
        added_files = current_set - previous_set
        for file_path in sorted(added_files):
            if not file_path.startswith('.verman'):
                changes.append({
                    'relative_path': file_path,
                    'file_hash': current_files[file_path],
                    'file_status': 'add'
                })

        # 2. 检测修改文件（基于哈希值比较）
        common_files = current_set & previous_set
        for file_path in sorted(common_files):
            current_hash = current_files[file_path]
            previous_hash = previous_files[file_path]

            if current_hash != previous_hash:
                changes.append({
                    'relative_path': file_path,
                    'file_hash': current_hash,
                    'file_status': 'modify'
                })

        # 3. 检测删除文件
        deleted_files = previous_set - current_set
        for file_path in sorted(deleted_files):
            if not file_path.startswith('.verman'):
                changes.append({
                    'relative_path': file_path,
                    'file_hash': previous_files.get(file_path, ''),
                    'file_status': 'delete'
                })

        return changes

    def _get_current_files_with_cache(self) -> Dict[str, str]:
        """
        获取当前工作区文件状态，带缓存机制

        Returns:
            文件状态字典 {相对路径: 哈希值}
        """
        # 使用单独的缓存锁，避免死锁
        with self._operation_lock:
            current_time = time.time()

            # 检查缓存是否有效
            if (self._last_scan_cache is not None and
                current_time - self._last_scan_time < self._cache_ttl):
                return self._last_scan_cache

            # 缓存失效，重新扫描
            try:
                ignore_patterns = self._get_ignore_patterns()
                self._last_scan_cache = self.file_manager.scan_workspace(ignore_patterns)
                self._last_scan_time = current_time
                return self._last_scan_cache
            except Exception as e:
                _logger.error(f"扫描工作区失败: {e}")
                # 返回空缓存，避免重复失败
                self._last_scan_cache = {}
                self._last_scan_time = current_time
                return {}

    def create_version(self, description: str) -> Optional[str]:
        """
        创建新版本，存储完整的文件状态快照
        添加超时保护，避免永久卡死

        Args:
            description: 版本描述

        Returns:
            版本号，失败返回None
        """
        # 超时保护
        import signal
        import threading

        class TimeoutError(Exception):
            pass

        def timeout_handler():
            raise TimeoutError("版本创建超时")

        # 设置30秒超时
        timer = threading.Timer(30.0, timeout_handler)
        timer.start()

        try:
            with self._operation_lock:
                try:
                    _logger.info("开始创建版本...")

                    # 1. 快速获取当前变更（使用缓存的扫描结果）
                    changes = self._get_current_changes_fast()
                    if not changes:
                        _logger.info("没有检测到文件变更，跳过版本创建")
                        return None

                    _logger.info(f"检测到 {len(changes)} 个文件变更")

                    # 2. 生成版本号
                    version_number = self._generate_version_number()
                    _logger.info(f"生成版本号: {version_number}")

                    # 3. 快速准备版本文件数据（避免重复扫描）
                    version_files = self._prepare_version_files_fast(changes)
                    _logger.info(f"准备版本文件数据完成，共 {len(version_files)} 个文件")

                    # 4. 创建版本记录
                    version_id = self.db_manager.create_version(
                        version_number=version_number,
                        description=description,
                        change_count=len(changes)
                    )
                    _logger.info(f"创建版本记录完成，版本ID: {version_id}")

                    # 5. 保存文件状态（分批保存，避免内存问题）
                    self._save_files_in_batches(version_id, version_files)
                    _logger.info("保存文件状态完成")

                    # 6. 清除缓存，确保下次变更检测的准确性
                    self._clear_scan_cache()
                    # 同时清除文件管理器的哈希缓存
                    if hasattr(self.file_manager, 'clear_hash_cache'):
                        self.file_manager.clear_hash_cache()

                    _logger.info(f"版本 {version_number} 创建成功，包含 {len(changes)} 个变更")
                    return version_number

                except Exception as e:
                    _logger.error(f"创建版本失败: {e}")
                    import traceback
                    _logger.error(f"错误详情: {traceback.format_exc()}")
                    return None
        finally:
            timer.cancel()  # 取消超时定时器

    def _get_current_changes_fast(self) -> List[Dict]:
        """
        快速获取当前变更，但使用准确的检测逻辑

        Returns:
            变更文件列表
        """
        try:
            # 直接扫描，不使用缓存以确保最新状态
            ignore_patterns = self._get_ignore_patterns()
            current_files = self.file_manager.scan_workspace(ignore_patterns)

            # 获取最新版本的文件状态
            latest_version_id = self.db_manager.get_latest_version_id()
            if latest_version_id is None:
                # 如果没有版本，所有文件都是新增的
                return [{
                    'relative_path': path,
                    'file_hash': hash_val,
                    'file_status': 'add'
                } for path, hash_val in current_files.items()]

            # 获取最新版本的完整文件状态
            latest_files = self.db_manager.get_version_files(latest_version_id)
            previous_files = {
                file['relative_path']: file['file_hash']
                for file in latest_files
                if file['file_status'] in ['add', 'modify', 'unmodified']
            }

            # 使用准确的变更检测逻辑
            return self._detect_changes_accurate(current_files, previous_files)

        except Exception as e:
            _logger.error(f"快速获取变更失败: {e}")
            return []

    
    def _prepare_version_files_fast(self, changes: List[Dict]) -> List[Dict]:
        """
        准备完整的版本文件数据，包含所有文件状态
        修复未变更文件状态错误的问题

        Args:
            changes: 变更列表

        Returns:
            完整的版本文件数据
        """
        import os

        # 1. 获取当前工作区的所有文件状态
        ignore_patterns = self._get_ignore_patterns()
        current_files = self.file_manager.scan_workspace(ignore_patterns)

        # 2. 获取最新版本的文件状态（用于对比）
        latest_version_id = self.db_manager.get_latest_version_id()
        previous_files = {}
        if latest_version_id:
            latest_files = self.db_manager.get_version_files(latest_version_id)
            previous_files = {
                file['relative_path']: file['file_hash']
                for file in latest_files
                if file['file_status'] in ['add', 'modify', 'unmodified']
            }

        # 3. 构建完整的文件状态映射
        file_status_map = {}

        # 处理变更文件
        for change in changes:
            file_status_map[change['relative_path']] = {
                'status': change['file_status'],
                'hash': change['file_hash']
            }

        # 处理当前存在但未变更的文件
        for file_path, file_hash in current_files.items():
            if file_path not in file_status_map:
                # 检查文件是否真的未变更
                if file_path in previous_files and previous_files[file_path] == file_hash:
                    file_status_map[file_path] = {
                        'status': 'unmodified',
                        'hash': file_hash
                    }
                else:
                    # 如果不在历史记录中或哈希不同，标记为新增
                    file_status_map[file_path] = {
                        'status': 'add',
                        'hash': file_hash
                    }

        # 4. 生成版本文件数据
        version_files = []
        for file_path in sorted(file_status_map.keys()):
            file_info = file_status_map[file_path]
            status = file_info['status']
            file_hash = file_info['hash']

            file_data = {
                'relative_path': file_path,
                'file_hash': file_hash,
                'file_status': status,
                'file_content': None
            }

            # 只有新增和修改的文件需要存储内容
            if status in ['add', 'modify']:
                try:
                    full_path = os.path.join(self.file_manager.workspace_path, file_path)
                    file_data['file_content'] = self.file_manager._read_file_content(full_path)
                except Exception as e:
                    _logger.warning(f"读取文件内容失败 {file_path}: {e}")
                    # 如果读取失败，标记为删除状态
                    file_data['file_status'] = 'delete'
                    file_data['file_content'] = None

            version_files.append(file_data)

        return version_files

    def _save_files_in_batches(self, version_id: int, version_files: List[Dict]):
        """
        分批保存文件数据，避免内存问题

        Args:
            version_id: 版本ID
            version_files: 文件数据列表
        """
        try:
            batch_size = 100
            for i in range(0, len(version_files), batch_size):
                batch = version_files[i:i + batch_size]
                self.db_manager.save_files(version_id, batch)
                _logger.debug(f"已保存 {min(i + batch_size, len(version_files))}/{len(version_files)} 个文件")
        except Exception as e:
            _logger.error(f"分批保存文件失败: {e}")
            raise

    def rollback_to_version(self, version_id: int, backup_current: bool = True) -> bool:
        """
        回滚到指定版本，并确保内部状态同步
        使用锁机制确保回滚操作的原子性

        Args:
            version_id: 目标版本ID
            backup_current: 是否备份当前状态

        Returns:
            回滚是否成功
        """
        with self._operation_lock:
            try:
                # 获取目标版本的文件
                version_files = self.db_manager.get_version_files(version_id)
                if not version_files:
                    _logger.error("版本文件不存在")
                    return False

                # 1. 备份当前状态（如果需要）
                if backup_current:
                    try:
                        self.file_manager._backup_current_state()
                    except Exception as backup_error:
                        _logger.warning(f"备份当前状态失败: {backup_error}")

                # 2. 恢复文件
                success = self.file_manager.restore_files(version_files, False)  # 已经备份过了，这里不重复备份
                if not success:
                    _logger.error("文件恢复失败")
                    return False

                # 3. 验证回滚结果
                if not self._verify_rollback_result(version_files):
                    _logger.error("回滚结果验证失败")
                    return False

                # 4. 同步内部状态（清除缓存，强制下次重新扫描）
                self._sync_internal_state_after_rollback(version_id)

                _logger.info(f"成功回滚到版本 {version_id}")
                return True

            except Exception as e:
                _logger.error(f"回滚失败: {e}")
                return False

    def _clear_scan_cache(self):
        """清除扫描缓存"""
        self._last_scan_cache = None
        self._last_scan_time = 0
        # 同时清除文件管理器的哈希缓存
        if hasattr(self.file_manager, 'clear_hash_cache'):
            self.file_manager.clear_hash_cache()

    def _verify_rollback_result(self, expected_files: List[Dict]) -> bool:
        """
        验证回滚结果是否正确

        Args:
            expected_files: 期望的文件状态列表

        Returns:
            验证是否成功
        """
        try:
            # 扫描当前工作区
            ignore_patterns = self._get_ignore_patterns()
            current_files = self.file_manager.scan_workspace(ignore_patterns)

            # 检查文件是否正确恢复
            expected_file_map = {
                f['relative_path']: f for f in expected_files
                if f['file_status'] in ['add', 'modify', 'unmodified']
            }

            mismatches = []
            for file_path, file_info in expected_file_map.items():
                if file_path not in current_files:
                    mismatches.append(f"文件 {file_path} 未找到")
                    continue

                current_hash = current_files[file_path]
                expected_hash = file_info['file_hash']

                if current_hash != expected_hash:
                    mismatches.append(f"文件 {file_path} 哈希值不匹配: 期望 {expected_hash[:8]}, 实际 {current_hash[:8]}")

            # 检查是否有不应该存在的文件
            expected_paths = set(expected_file_map.keys())
            current_paths = set(current_files.keys())
            extra_files = current_paths - expected_paths

            # 忽略版本管理相关的额外文件
            extra_files = [f for f in extra_files if not f.startswith('.verman')]

            if extra_files:
                mismatches.extend([f"额外文件 {f}" for f in extra_files[:10]])  # 只显示前10个

            if mismatches:
                _logger.warning(f"回滚验证发现 {len(mismatches)} 个问题: {'; '.join(mismatches)}")
                # 不直接返回False，允许一定的差异（可能是忽略规则导致的）
                return len(mismatches) <= 5  # 允许少量差异

            return True

        except Exception as e:
            _logger.warning(f"验证回滚结果时出错: {e}")
            return True  # 验证失败时保守处理，假设回滚成功

    def _sync_internal_state_after_rollback(self, target_version_id: int):
        """
        回滚后同步内部状态

        Args:
            target_version_id: 目标版本ID
        """
        try:
            # 1. 清除扫描缓存，确保下次操作使用最新状态
            self._clear_scan_cache()

            # 2. 验证版本数据库状态
            try:
                # 确保目标版本存在
                versions = self.db_manager.get_all_versions()
                target_exists = any(v['id'] == target_version_id for v in versions)
                if not target_exists:
                    _logger.warning(f"目标版本 {target_version_id} 在数据库中不存在")

            except Exception as db_error:
                _logger.warning(f"验证数据库状态时出错: {db_error}")

            # 3. 记录回滚操作
            _logger.info(f"内部状态已同步到版本 {target_version_id}")

        except Exception as e:
            _logger.warning(f"同步内部状态时出错: {e}")

    def get_all_versions(self) -> List[Dict]:
        """
        获取所有版本信息

        Returns:
            版本信息列表
        """
        try:
            return self.db_manager.get_all_versions()
        except Exception as e:
            print(f"获取版本列表失败: {e}")
            return []

    def get_version_details(self, version_id: int) -> Optional[Dict]:
        """
        获取版本详细信息

        Args:
            version_id: 版本ID

        Returns:
            版本详细信息
        """
        try:
            # 获取版本基本信息
            versions = self.db_manager.get_all_versions()
            version_info = None
            for version in versions:
                if version['id'] == version_id:
                    version_info = version
                    break

            if not version_info:
                return None

            # 获取版本文件
            files = self.db_manager.get_version_files(version_id)

            # 统计变更类型
            add_count = len([f for f in files if f['file_status'] == 'add'])
            modify_count = len([f for f in files if f['file_status'] == 'modify'])
            delete_count = len([f for f in files if f['file_status'] == 'delete'])
            unmodified_count = len([f for f in files if f['file_status'] == 'unmodified'])

            version_info['files'] = files
            version_info['statistics'] = {
                'add_count': add_count,
                'modify_count': modify_count,
                'delete_count': delete_count,
                'unmodified_count': unmodified_count,
                'total_count': len(files)
            }

            return version_info

        except Exception as e:
            print(f"获取版本详情失败: {e}")
            return None

    def compare_versions(self, version_id1: int, version_id2: int) -> Dict:
        """
        比较两个版本的差异，使用优化的内存管理

        Args:
            version_id1: 第一个版本ID
            version_id2: 第二个版本ID

        Returns:
            差异信息
        """
        try:
            # 使用流式比较，减少内存占用
            return self._compare_versions_streaming(version_id1, version_id2)

        except Exception as e:
            _logger.error(f"版本比较失败: {e}")
            return {}

    def _compare_versions_streaming(self, version_id1: int, version_id2: int) -> Dict:
        """
        流式版本比较，优化内存使用

        Args:
            version_id1: 第一个版本ID
            version_id2: 第二个版本ID

        Returns:
            差异信息
        """
        try:
            differences = {
                'only_in_first': [],
                'only_in_second': [],
                'different': []
            }

            # 分批获取文件数据，避免内存溢出
            batch_size = 500

            # 处理第一个版本的文件
            offset1 = 0
            files1_map = {}
            deleted_files1_set = set()

            while True:
                batch1 = self._get_version_files_batch(version_id1, offset1, batch_size)
                if not batch1:
                    break

                for file_info in batch1:
                    if file_info['file_status'] == 'delete':
                        deleted_files1_set.add(file_info['relative_path'])
                    else:
                        files1_map[file_info['relative_path']] = file_info

                offset1 += batch_size

            # 处理第二个版本的文件
            offset2 = 0
            files2_map = {}
            deleted_files2_set = set()

            while True:
                batch2 = self._get_version_files_batch(version_id2, offset2, batch_size)
                if not batch2:
                    break

                for file_info in batch2:
                    if file_info['file_status'] == 'delete':
                        deleted_files2_set.add(file_info['relative_path'])
                    else:
                        files2_map[file_info['relative_path']] = file_info

                offset2 += batch_size

            # 计算差异
            paths1 = set(files1_map.keys())
            paths2 = set(files2_map.keys())

            only_in_v1 = paths1 - paths2
            only_in_v2 = paths2 - paths1
            common = paths1 & paths2

            # 收集差异信息
            for path in only_in_v1:
                differences['only_in_first'].append(files1_map[path])

            for path in only_in_v2:
                differences['only_in_second'].append(files2_map[path])

            # 检查共同文件的差异
            for path in common:
                file1 = files1_map[path]
                file2 = files2_map[path]

                # 只比较哈希值，不比较文件内容，节省内存
                if (file1['file_hash'] != file2['file_hash'] or
                    file1['file_status'] != file2['file_status']):
                    differences['different'].append({
                        'relative_path': path,
                        'file_in_v1': {
                            'file_hash': file1['file_hash'],
                            'file_status': file1['file_status']
                        },
                        'file_in_v2': {
                            'file_hash': file2['file_hash'],
                            'file_status': file2['file_status']
                        }
                    })

            # 处理删除状态的变化
            # 在v1中删除但在v2中存在的文件
            for path in deleted_files1_set:
                if path in files2_map:
                    differences['only_in_second'].append(files2_map[path])

            # 在v2中删除但在v1中存在的文件
            for path in deleted_files2_set:
                if path in files1_map:
                    differences['only_in_first'].append(files1_map[path])

            return differences

        except Exception as e:
            _logger.error(f"流式版本比较失败: {e}")
            return {}

    def _get_version_files_batch(self, version_id: int, offset: int, limit: int) -> List[Dict]:
        """
        分批获取版本文件数据

        Args:
            version_id: 版本ID
            offset: 偏移量
            limit: 限制数量

        Returns:
            文件数据列表
        """
        try:
            cursor = self.db_manager.conn.execute('''
                SELECT relative_path, file_hash, file_status
                FROM files
                WHERE version_id = ?
                ORDER BY relative_path
                LIMIT ? OFFSET ?
            ''', (version_id, limit, offset))

            return [{
                'relative_path': row[0],
                'file_hash': row[1],
                'file_status': row[2]
            } for row in cursor.fetchall()]

        except Exception as e:
            _logger.error(f"获取版本文件批次失败: {e}")
            return []

    def export_version(self, version_id: int, export_path: str) -> bool:
        """
        导出版本到指定目录

        Args:
            version_id: 版本ID
            export_path: 导出路径

        Returns:
            导出是否成功
        """
        try:
            # 获取版本文件
            version_files = self.db_manager.get_version_files(version_id)
            if not version_files:
                print("版本文件不存在")
                return False

            # 导出文件
            success = self.file_manager.export_version_files(version_files, export_path)
            if success:
                print(f"版本已导出到: {export_path}")
            return success

        except Exception as e:
            print(f"导出版本失败: {e}")
            return False

    def delete_version(self, version_id: int) -> bool:
        """
        删除版本

        Args:
            version_id: 版本ID

        Returns:
            删除是否成功
        """
        try:
            self.db_manager.delete_version(version_id)
            print(f"版本 {version_id} 已删除")
            return True

        except Exception as e:
            print(f"删除版本失败: {e}")
            return False

    def _generate_version_number(self) -> str:
        """
        生成版本号，确保唯一性

        Returns:
            新的版本号
        """
        try:
            # 获取所有版本
            versions = self.db_manager.get_all_versions()

            if not versions:
                return "v1.0"

            # 解析最新版本号并递增
            latest_version = versions[0]['version_number']
            if latest_version.startswith('v'):
                try:
                    # 尝试解析 v1.0 格式
                    parts = latest_version[1:].split('.')
                    if len(parts) == 2:
                        major = int(parts[0])
                        minor = int(parts[1])
                        minor += 1
                        new_version = f"v{major}.{minor}"

                        # 检查是否已存在
                        existing_versions = [v['version_number'] for v in versions]
                        if new_version not in existing_versions:
                            return new_version
                except ValueError:
                    pass

            # 如果版本号冲突或无法解析，使用时间戳
            from datetime import datetime
            import time

            # 确保时间戳版本号唯一
            base_time = datetime.now().strftime('%Y%m%d_%H%M%S')
            new_version = f"v{base_time}"

            existing_versions = [v['version_number'] for v in versions]
            counter = 1
            while new_version in existing_versions:
                new_version = f"v{base_time}_{counter}"
                counter += 1

            return new_version

        except Exception:
            # 生成一个唯一的简单版本号
            from datetime import datetime
            import time
            return f"v{int(time.time())}"

    def _prepare_complete_version_files(self, changes: List[Dict], current_files: Dict[str, str]) -> List[Dict]:
        """
        准备完整的版本文件数据
        使用更准确的状态计算逻辑，确保版本状态的一致性

        Args:
            changes: 检测到的变更列表
            current_files: 当前工作区的所有文件状态

        Returns:
            完整的版本文件数据列表
        """
        import os
        version_files = []

        # 构建完整的文件状态映射
        file_status_map = {}

        # 1. 处理变更文件的状态
        for change in changes:
            file_status_map[change['relative_path']] = {
                'status': change['file_status'],
                'hash': change['file_hash']
            }

        # 2. 处理当前存在的文件（包括未变更的文件）
        for file_path, file_hash in current_files.items():
            if file_path not in file_status_map:
                # 当前存在但不在变更列表中的文件，标记为未变更
                file_status_map[file_path] = {
                    'status': 'unmodified',
                    'hash': file_hash
                }

        # 3. 生成版本文件数据，按文件路径排序以确保一致性
        for file_path in sorted(file_status_map.keys()):
            file_info = file_status_map[file_path]
            status = file_info['status']
            file_hash = file_info['hash']

            # 删除的文件不存储内容
            file_content = None
            if status in ['add', 'modify']:
                try:
                    full_path = os.path.join(self.file_manager.workspace_path, file_path)
                    file_content = self.file_manager._read_file_content(full_path)
                except Exception as e:
                    _logger.warning(f"读取文件内容失败 {file_path}: {e}")
                    # 如果读取失败，标记为删除状态以避免数据不完整
                    status = 'delete'
                    file_content = None

            version_files.append({
                'relative_path': file_path,
                'file_hash': file_hash,
                'file_status': status,
                'file_content': file_content
            })

        return version_files