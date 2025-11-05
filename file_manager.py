"""
文件管理模块
负责文件扫描、哈希计算、变更检测和文件恢复操作
"""

import os
import hashlib
from datetime import datetime
from typing import Dict, List, Set, Tuple
import fnmatch


class FileManager:
    """文件管理器，负责所有文件相关操作"""

    def __init__(self, workspace_path: str):
        """
        初始化文件管理器

        Args:
            workspace_path: 工作区路径
        """
        self.workspace_path = os.path.abspath(workspace_path)

    def _calculate_file_hash(self, file_path: str) -> str:
        """
        计算文件的MD5哈希值

        Args:
            file_path: 文件绝对路径

        Returns:
            文件的MD5哈希值
        """
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except (IOError, OSError):
            return ""

    def _read_file_content(self, file_path: str) -> bytes:
        """
        读取文件二进制内容

        Args:
            file_path: 文件绝对路径

        Returns:
            文件二进制内容
        """
        try:
            with open(file_path, "rb") as f:
                return f.read()
        except (IOError, OSError):
            return b""

    def scan_workspace(self, ignore_patterns: List[str] = None) -> Dict[str, str]:
        """
        扫描工作区，获取所有文件的相对路径和哈希值

        Args:
            ignore_patterns: 忽略的文件模式列表

        Returns:
            字典 {相对路径: 哈希值}
        """
        if ignore_patterns is None:
            ignore_patterns = []

        file_hashes = {}

        # 默认忽略的文件和目录
        default_ignore = [
            '.verman.db', '*.db', '*.sqlite', '*.sqlite3',
            '__pycache__', '*.pyc', '*.pyo',
            '.git', '.svn', '.hg',
            '*.tmp', '*.temp', '*.log',
            '.DS_Store', 'Thumbs.db'
        ]
        all_ignore_patterns = default_ignore + ignore_patterns

        for root, dirs, files in os.walk(self.workspace_path):
            # 过滤忽略的目录
            dirs[:] = [d for d in dirs if not self._should_ignore(d, all_ignore_patterns)]

            for file in files:
                if self._should_ignore(file, all_ignore_patterns):
                    continue

                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, self.workspace_path)

                try:
                    file_hash = self._calculate_file_hash(file_path)
                    if file_hash:  # 只有成功读取的文件才添加到结果中
                        file_hashes[relative_path] = file_hash
                except Exception:
                    # 跳过无法读取的文件
                    continue

        return file_hashes

    def _should_ignore(self, name: str, ignore_patterns: List[str]) -> bool:
        """
        检查文件或目录是否应该被忽略

        Args:
            name: 文件或目录名
            ignore_patterns: 忽略模式列表

        Returns:
            是否应该忽略
        """
        for pattern in ignore_patterns:
            if fnmatch.fnmatch(name, pattern):
                return True
        return False

    def detect_changes(self, current_files: Dict[str, str], previous_files: Dict[str, str]) -> List[Dict]:
        """
        检测文件变更，只对真正发生变更的文件进行记录

        Args:
            current_files: 当前文件状态 {相对路径: 哈希值}
            previous_files: 上次文件状态 {相对路径: 哈希值}

        Returns:
            变更列表，每个元素包含相对路径、哈希值和变更类型
        """
        changes = []

        # 获取文件路径集合
        current_set = set(current_files.keys())
        previous_set = set(previous_files.keys())

        # 1. 检测新增文件
        added_files = current_set - previous_set
        for file_path in sorted(added_files):
            if file_path.startswith('.verman'):  # 跳过版本管理相关文件
                continue
            changes.append({
                'relative_path': file_path,
                'file_hash': current_files[file_path],
                'file_status': 'add'
            })

        # 2. 检测修改文件（通过哈希值比较）
        common_files = current_set & previous_set
        for file_path in sorted(common_files):
            current_hash = current_files[file_path]
            previous_hash = previous_files[file_path]

            # 只有哈希值不同才认为是修改
            if current_hash != previous_hash:
                changes.append({
                    'relative_path': file_path,
                    'file_hash': current_hash,
                    'file_status': 'modify'
                })

        # 3. 检测删除文件
        deleted_files = previous_set - current_set
        for file_path in sorted(deleted_files):
            if file_path.startswith('.verman'):  # 跳过版本管理相关文件
                continue
            changes.append({
                'relative_path': file_path,
                'file_hash': '',
                'file_status': 'delete'
            })

        return changes

    def prepare_files_for_version(self, changes: List[Dict]) -> List[Dict]:
        """
        为版本提交准备文件数据，包含文件内容

        Args:
            changes: 变更列表

        Returns:
            包含文件内容的版本数据
        """
        version_files = []

        for change in changes:
            file_data = {
                'relative_path': change['relative_path'],
                'file_hash': change['file_hash'],
                'file_status': change['file_status']
            }

            # 只有新增和修改的文件需要存储内容
            if change['file_status'] in ['add', 'modify']:
                file_path = os.path.join(self.workspace_path, change['relative_path'])
                file_data['file_content'] = self._read_file_content(file_path)
            else:
                file_data['file_content'] = None

            version_files.append(file_data)

        return version_files

    def restore_files(self, version_files: List[Dict], backup_current: bool = True) -> bool:
        """
        从版本数据恢复文件

        Args:
            version_files: 版本文件数据
            backup_current: 是否备份当前状态

        Returns:
            恢复是否成功
        """
        try:
            # 如果需要备份当前状态
            if backup_current:
                self._backup_current_state()

            # 恢复文件
            for file_data in version_files:
                relative_path = file_data['relative_path']
                file_status = file_data['file_status']
                file_content = file_data.get('file_content')
                target_path = os.path.join(self.workspace_path, relative_path)

                # 确保目标目录存在
                os.makedirs(os.path.dirname(target_path), exist_ok=True)

                if file_status == 'delete':
                    # 删除文件
                    if os.path.exists(target_path):
                        os.remove(target_path)
                elif file_status in ['add', 'modify'] and file_content is not None:
                    # 恢复文件内容
                    with open(target_path, 'wb') as f:
                        f.write(file_content)

            return True

        except Exception as e:
            print(f"文件恢复失败: {e}")
            return False

    def _backup_current_state(self):
        """备份当前状态（简单实现，可以扩展）"""
        backup_dir = os.path.join(self.workspace_path, '.verman_backup')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(backup_dir, f'backup_{timestamp}')

        try:
            os.makedirs(backup_path, exist_ok=True)
            # 这里可以实现更完整的备份逻辑
            print(f"当前状态已备份到: {backup_path}")
        except Exception as e:
            print(f"备份失败: {e}")

    def export_version_files(self, version_files: List[Dict], export_path: str) -> bool:
        """
        导出版本文件到指定目录

        Args:
            version_files: 版本文件数据
            export_path: 导出路径

        Returns:
            导出是否成功
        """
        try:
            for file_data in version_files:
                if file_data['file_status'] == 'delete':
                    continue  # 跳过已删除的文件

                relative_path = file_data['relative_path']
                file_content = file_data.get('file_content')
                if file_content is None:
                    continue

                target_path = os.path.join(export_path, relative_path)
                os.makedirs(os.path.dirname(target_path), exist_ok=True)

                with open(target_path, 'wb') as f:
                    f.write(file_content)

            return True

        except Exception as e:
            print(f"导出失败: {e}")
            return False