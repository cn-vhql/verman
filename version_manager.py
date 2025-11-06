"""
版本管理模块
负责版本创建、提交、回滚和查询等核心功能
"""

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

    def __init__(self, db_manager: DatabaseManager, file_manager: FileManager):
        """
        初始化版本管理器

        Args:
            db_manager: 数据库管理器
            file_manager: 文件管理器
        """
        self.db_manager = db_manager
        self.file_manager = file_manager

    def get_current_changes(self) -> List[Dict]:
        """
        获取当前工作区的变更文件
        通过与最新版本的哈希值比对，只检测真正发生变更的文件

        Returns:
            变更文件列表
        """
        try:
            # 1. 扫描当前工作区，获取所有文件的哈希值
            current_files = self.file_manager.scan_workspace()

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
                if file['file_status'] in ['add', 'modify', 'unmodified']  # 包含所有实际存在的文件
            }

            # 4. 检测变更（基于哈希值比对）
            changes = self.file_manager.detect_changes(current_files, previous_files)
            return changes

        except Exception as e:
            _logger.error(f"获取变更失败: {e}")
            return []

    def create_version(self, description: str) -> Optional[str]:
        """
        创建新版本，存储完整的文件状态快照
        每个版本都包含当前所有文件的状态信息，确保后续版本能正确比对

        Args:
            description: 版本描述

        Returns:
            版本号，失败返回None
        """
        try:
            # 1. 获取当前变更（基于哈希比对）
            changes = self.get_current_changes()
            if not changes:
                return None

            # 2. 生成版本号
            version_number = self._generate_version_number()

            # 3. 获取当前完整的文件状态
            current_files = self.file_manager.scan_workspace()

            # 4. 准备版本文件数据（包含完整的文件状态）
            version_files = self._prepare_complete_version_files(changes, current_files)

            # 5. 创建版本记录
            version_id = self.db_manager.create_version(
                version_number=version_number,
                description=description,
                change_count=len(changes)
            )

            # 6. 保存完整的文件状态
            self.db_manager.save_files(version_id, version_files)

            return version_number

        except Exception as e:
            _logger.error(f"创建版本失败: {e}")
            return None

    def rollback_to_version(self, version_id: int, backup_current: bool = True) -> bool:
        """
        回滚到指定版本

        Args:
            version_id: 目标版本ID
            backup_current: 是否备份当前状态

        Returns:
            回滚是否成功
        """
        try:
            # 获取目标版本的文件
            version_files = self.db_manager.get_version_files(version_id)
            if not version_files:
                _logger.error("版本文件不存在")
                return False

            # 恢复文件
            success = self.file_manager.restore_files(version_files, backup_current)
            if success:
                _logger.info(f"成功回滚到版本 {version_id}")
            return success

        except Exception as e:
            _logger.error(f"回滚失败: {e}")
            return False

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
        比较两个版本的差异

        Args:
            version_id1: 第一个版本ID
            version_id2: 第二个版本ID

        Returns:
            差异信息
        """
        try:
            # 获取两个版本的文件
            files1 = self.db_manager.get_version_files(version_id1)
            files2 = self.db_manager.get_version_files(version_id2)

            # 转换为字典方便比较，排除删除状态进行路径比较
            dict1 = {f['relative_path']: f for f in files1 if f['file_status'] != 'delete'}
            dict2 = {f['relative_path']: f for f in files2 if f['file_status'] != 'delete'}

            # 获取删除文件
            deleted_files1 = {f['relative_path']: f for f in files1 if f['file_status'] == 'delete'}
            deleted_files2 = {f['relative_path']: f for f in files2 if f['file_status'] == 'delete'}

            # 计算差异
            paths1 = set(dict1.keys())
            paths2 = set(dict2.keys())
            deleted_paths1 = set(deleted_files1.keys())
            deleted_paths2 = set(deleted_files2.keys())

            only_in_v1 = paths1 - paths2
            only_in_v2 = paths2 - paths1
            common = paths1 & paths2

            differences = {
                'only_in_first': [dict1[path] for path in only_in_v1],
                'only_in_second': [dict2[path] for path in only_in_v2],
                'different': []
            }

            # 检查共同文件的差异（内容变化）
            for path in common:
                file1 = dict1[path]
                file2 = dict2[path]

                # 检查哈希值或状态是否变化
                if (file1['file_hash'] != file2['file_hash'] or
                    file1['file_status'] != file2['file_status']):
                    differences['different'].append({
                        'relative_path': path,
                        'file_in_v1': file1,
                        'file_in_v2': file2
                    })

            # 检查删除状态的变化
            # 在v1中删除但在v2中存在的文件
            for path in deleted_paths1:
                if path in dict2:  # v2中存在
                    differences['only_in_second'].append(dict2[path])

            # 在v2中删除但在v1中存在的文件
            for path in deleted_paths2:
                if path in dict1:  # v1中存在
                    differences['only_in_first'].append(dict1[path])

            return differences

        except Exception as e:
            _logger.error(f"版本比较失败: {e}")
            return {}

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
        包含所有当前文件的状态信息，而不仅仅是变更的文件

        Args:
            changes: 检测到的变更列表
            current_files: 当前工作区的所有文件状态

        Returns:
            完整的版本文件数据列表
        """
        import os
        version_files = []

        # 创建变更文件的映射，便于查找，删除文件优先级最高
        change_map = {
            change['relative_path']: change['file_status']
            for change in changes
        }

        # 1. 先处理被删除的文件（优先级最高，避免重复）
        processed_files = set()
        for change in changes:
            if change['file_status'] == 'delete':
                version_files.append({
                    'relative_path': change['relative_path'],
                    'file_hash': change['file_hash'],
                    'file_status': 'delete',
                    'file_content': None  # 删除的文件不存储内容
                })
                processed_files.add(change['relative_path'])

        # 2. 处理当前存在的文件（排除已标记为删除的文件）
        for file_path, file_hash in current_files.items():
            if file_path in processed_files:
                continue  # 跳过已处理的删除文件

            status = change_map.get(file_path, 'unmodified')  # 未变更的文件

            # 只有新增和修改的文件需要存储内容
            file_content = None
            if status in ['add', 'modify']:
                full_path = os.path.join(self.file_manager.workspace_path, file_path)
                file_content = self.file_manager._read_file_content(full_path)

            version_files.append({
                'relative_path': file_path,
                'file_hash': file_hash,
                'file_status': status,
                'file_content': file_content
            })

        return version_files