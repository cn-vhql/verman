"""
文件管理模块
负责文件扫描、哈希计算、变更检测和文件恢复操作
"""

import os
import hashlib
from datetime import datetime
from typing import Dict, List, Set, Tuple
import fnmatch

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


class FileManager:
    """文件管理器，负责所有文件相关操作"""

    def __init__(self, workspace_path: str):
        """
        初始化文件管理器

        Args:
            workspace_path: 工作区路径
        """
        self.workspace_path = os.path.abspath(workspace_path)
        self._hash_cache = {}  # 文件哈希缓存 {相对路径: (哈希值, 修改时间)}
        self._cache_max_size = 1000  # 最大缓存条目数
        self._cache_ttl = 300  # 缓存5分钟

    def _calculate_file_hash(self, file_path: str, force_recalculate: bool = False) -> str:
        """
        计算文件的MD5哈希值，解决空文件哈希唯一性问题

        Args:
            file_path: 文件绝对路径
            force_recalculate: 是否强制重新计算

        Returns:
            文件的MD5哈希值
        """
        import time

        try:
            # 获取相对路径用于缓存键
            relative_path = os.path.relpath(file_path, self.workspace_path)

            # 如果不强制重新计算，检查缓存
            if not force_recalculate:
                cached_result = self._get_cached_hash(relative_path, file_path)
                if cached_result is not None:
                    return cached_result

            # 计算哈希值
            hash_md5 = hashlib.md5()
            file_size = os.path.getsize(file_path)

            with open(file_path, "rb") as f:
                if file_size == 0:
                    # 空文件特殊处理：结合文件路径生成唯一哈希
                    hash_md5.update(b"EMPTY_FILE:")
                    hash_md5.update(relative_path.encode('utf-8'))
                    hash_md5.update(str(os.path.getmtime(file_path)).encode('utf-8'))
                elif file_size < 10 * 1024 * 1024:  # 小于10MB的文件直接读取
                    for chunk in iter(lambda: f.read(4096), b""):
                        hash_md5.update(chunk)
                else:
                    # 大文件分块读取，显示进度
                    processed = 0
                    while True:
                        chunk = f.read(64 * 1024)  # 64KB块
                        if not chunk:
                            break
                        hash_md5.update(chunk)
                        processed += len(chunk)

            calculated_hash = hash_md5.hexdigest()

            # 更新缓存
            self._update_hash_cache(relative_path, calculated_hash, file_path)

            return calculated_hash

        except (IOError, OSError):
            return ""

    def _get_cached_hash(self, relative_path: str, file_path: str) -> str:
        """
        从缓存获取哈希值

        Args:
            relative_path: 相对路径
            file_path: 绝对路径

        Returns:
            缓存的哈希值，如果缓存无效返回None
        """
        try:
            if relative_path not in self._hash_cache:
                return None

            cached_hash, cached_time = self._hash_cache[relative_path]

            # 检查缓存是否过期
            import time
            current_time = time.time()
            if current_time - cached_time > self._cache_ttl:
                del self._hash_cache[relative_path]
                return None

            # 检查文件是否被修改
            file_mtime = os.path.getmtime(file_path)
            if file_mtime > cached_time:
                del self._hash_cache[relative_path]
                return None

            return cached_hash

        except (OSError, KeyError):
            # 出错时清除缓存条目
            self._hash_cache.pop(relative_path, None)
            return None

    def _update_hash_cache(self, relative_path: str, file_hash: str, file_path: str):
        """
        更新哈希缓存

        Args:
            relative_path: 相对路径
            file_hash: 文件哈希值
            file_path: 绝对路径
        """
        try:
            import time

            # 如果缓存过大，清理最旧的条目
            if len(self._hash_cache) >= self._cache_max_size:
                self._cleanup_hash_cache()

            # 添加新缓存条目
            current_time = time.time()
            self._hash_cache[relative_path] = (file_hash, current_time)

        except Exception as e:
            _logger.debug(f"更新哈希缓存失败 {relative_path}: {e}")

    def _cleanup_hash_cache(self):
        """清理哈希缓存，移除最旧的条目"""
        try:
            if not self._hash_cache:
                return

            # 按时间排序，移除最旧的25%
            sorted_items = sorted(
                self._hash_cache.items(),
                key=lambda x: x[1][1]  # 按时间排序
            )

            # 保留最新的75%
            keep_count = int(len(sorted_items) * 0.75)
            self._hash_cache = dict(sorted_items[keep_count:])

        except Exception as e:
            _logger.debug(f"清理哈希缓存失败: {e}")
            # 出错时清空缓存
            self._hash_cache.clear()

    def clear_hash_cache(self):
        """清空哈希缓存"""
        self._hash_cache.clear()

    def _read_file_content(self, file_path: str) -> bytes:
        """
        读取文件二进制内容，支持大文件处理

        Args:
            file_path: 文件绝对路径

        Returns:
            文件二进制内容
        """
        try:
            # 检查文件大小，避免处理过大的文件
            file_size = os.path.getsize(file_path)
            max_size = 50 * 1024 * 1024  # 50MB限制

            if file_size > max_size:
                raise ValueError(f"文件过大 ({file_size // 1024 // 1024}MB)，超过限制 ({max_size // 1024 // 1024}MB)")

            # 对于中等大小的文件，直接读取
            if file_size < 10 * 1024 * 1024:  # 10MB以下
                with open(file_path, "rb") as f:
                    return f.read()
            else:
                # 对于大文件，分块读取
                content = bytearray()
                with open(file_path, "rb") as f:
                    while True:
                        chunk = f.read(4096)
                        if not chunk:
                            break
                        content.extend(chunk)
                        # 检查内存使用
                        if len(content) > max_size:
                            raise ValueError(f"文件内容过大，超过内存限制")
                return bytes(content)

        except (IOError, OSError, ValueError) as e:
            _logger.error(f"读取文件失败 {file_path}: {e}")
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
            '.verman_backup', '.verman_temp',
            '__pycache__', '*.pyc', '*.pyo',
            '.git', '.svn', '.hg',
            '*.tmp', '*.temp', '*.log',
            '.DS_Store', 'Thumbs.db'
        ]

        # 从忽略文件加载自定义忽略规则
        ignore_file_patterns = self._load_ignore_file()

        # 合并所有忽略规则
        all_ignore_patterns = default_ignore + ignore_file_patterns + ignore_patterns

        # 安全检查：确保工作区路径存在且可访问
        if not os.path.exists(self.workspace_path):
            raise FileNotFoundError(f"工作区路径不存在: {self.workspace_path}")

        if not os.access(self.workspace_path, os.R_OK):
            raise PermissionError(f"工作区路径不可读: {self.workspace_path}")

        # 检查文件数量限制
        file_count = 0
        max_files = 10000  # 最大文件数限制

        for root, dirs, files in os.walk(self.workspace_path):
            # 安全检查：防止路径遍历攻击
            try:
                relative_root = os.path.relpath(root, self.workspace_path)
                if relative_root.startswith('..'):
                    continue  # 跳过工作区外的目录
            except ValueError:
                continue  # 路径解析错误，跳过

            # 过滤忽略的目录
            dirs[:] = [d for d in dirs if not self._should_ignore(d, all_ignore_patterns)]

            for file in files:
                if file_count >= max_files:
                    _logger.warning(f"文件数量超过限制 ({max_files})，停止扫描")
                    return file_hashes

                if self._should_ignore(file, all_ignore_patterns):
                    continue

                file_path = os.path.join(root, file)

                # 符号链接处理策略
                if os.path.islink(file_path):
                    try:
                        # 获取符号链接的目标路径
                        link_target = os.path.realpath(file_path)

                        # 检查目标是否在工作区内
                        target_relative = os.path.relpath(link_target, self.workspace_path)
                        if (target_relative.startswith('..') or
                            os.path.isabs(link_target) and not link_target.startswith(self.workspace_path)):
                            # 链接指向工作区外部，跳过
                            _logger.debug(f"跳过外部链接 {file_path} -> {link_target}")
                            continue

                        # 使用链接路径作为相对路径，但指向实际文件
                        file_path = link_target

                    except (OSError, ValueError):
                        # 无效链接，跳过
                        _logger.debug(f"跳过无效链接 {file_path}")
                        continue

                # 安全检查：文件路径
                try:
                    relative_path = os.path.relpath(file_path, self.workspace_path)
                    if (relative_path.startswith('..') or
                        '..' in relative_path.split(os.sep) or
                        os.path.isabs(relative_path)):
                        continue  # 跳过不安全的路径
                except ValueError:
                    continue  # 路径解析错误，跳过

                try:
                    # 检查文件访问权限
                    if not os.access(file_path, os.R_OK):
                        continue  # 跳过无权限的文件

                    # 检查文件大小
                    file_size = os.path.getsize(file_path)
                    if file_size > 100 * 1024 * 1024:  # 100MB限制
                        _logger.warning(f"跳过过大文件 {relative_path} ({file_size // 1024 // 1024}MB)")
                        continue

                    file_hash = self._calculate_file_hash(file_path)
                    if file_hash:  # 只有成功读取的文件才添加到结果中
                        file_hashes[relative_path] = file_hash
                        file_count += 1

                except (OSError, IOError, ValueError) as e:
                    # 跳过有问题的文件
                    _logger.warning(f"跳过文件 {relative_path}: {e}")
                    continue

        return file_hashes

    def _load_ignore_file(self) -> List[str]:
        """
        从.vermanignore文件加载忽略规则

        Returns:
            忽略规则列表
        """
        ignore_file_path = os.path.join(self.workspace_path, '.vermanignore')
        patterns = []

        try:
            if os.path.exists(ignore_file_path):
                with open(ignore_file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        # 跳过空行和注释行
                        if line and not line.startswith('#'):
                            patterns.append(line)
        except (IOError, OSError, UnicodeDecodeError) as e:
            _logger.warning(f"读取忽略文件失败: {e}")

        return patterns

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
        检测文件变更，使用增强的删除检测机制

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

        # 3. 检测删除文件（使用增强的确认机制）
        deleted_files = previous_set - current_set
        for file_path in sorted(deleted_files):
            if file_path.startswith('.verman'):  # 跳过版本管理相关文件
                continue

            # 确认文件真的被删除（而不是临时移动）
            if self._confirm_file_deletion(file_path, previous_files.get(file_path, '')):
                # 保留删除文件的原始哈希值，用于后续版本比较
                original_hash = previous_files.get(file_path, '')
                changes.append({
                    'relative_path': file_path,
                    'file_hash': original_hash,
                    'file_status': 'delete'
                })
            else:
                # 文件可能被临时移动，不记录为删除
                _logger.info(f"文件 {file_path} 可能被临时移动，暂不记录为删除")

        return changes

    def _confirm_file_deletion(self, file_path: str, original_hash: str) -> bool:
        """
        确认文件是否真的被删除，避免延迟累积

        Args:
            file_path: 文件相对路径
            original_hash: 文件原始哈希值

        Returns:
            文件是否真的被删除
        """
        import os

        try:
            full_path = os.path.join(self.workspace_path, file_path)

            # 1. 检查文件是否真的不存在
            if os.path.exists(full_path):
                return False  # 文件存在，不是删除

            # 2. 检查是否是临时移动（检查回收站或备份目录）
            if self._is_file_temporarily_moved(file_path, original_hash):
                return False

            # 3. 移除延迟机制，避免卡死
            # 如果文件不存在且不在临时位置，直接确认为删除
            return True  # 确认文件被删除

        except Exception as e:
            _logger.warning(f"确认文件删除状态时出错 {file_path}: {e}")
            # 出错时保守处理，假设文件被删除
            return True

    def _is_file_temporarily_moved(self, file_path: str, original_hash: str) -> bool:
        """
        检查文件是否被临时移动到其他位置

        Args:
            file_path: 文件相对路径
            original_hash: 文件原始哈希值

        Returns:
            文件是否被临时移动
        """
        if not original_hash:
            return False

        try:
            # 检查常见的临时位置
            temp_locations = [
                '.verman_backup',
                '.verman_temp',
                'temp', 'tmp',
                os.path.expanduser('~/.Trash'),
                os.path.expanduser('~/Desktop'),
            ]

            # 检查工作区内的临时目录
            for temp_dir in temp_locations:
                temp_path = os.path.join(self.workspace_path, temp_dir)
                if os.path.exists(temp_path):
                    if self._search_file_by_hash(temp_path, original_hash, file_path):
                        _logger.debug(f"在临时目录 {temp_dir} 中找到文件 {file_path}")
                        return True

            # 检查系统临时目录
            import tempfile
            system_temp = tempfile.gettempdir()
            if self._search_file_by_hash(system_temp, original_hash, file_path):
                _logger.debug(f"在系统临时目录中找到文件 {file_path}")
                return True

            return False

        except Exception as e:
            _logger.debug(f"检查文件临时移动时出错 {file_path}: {e}")
            return False

    def _search_file_by_hash(self, search_path: str, target_hash: str, original_name: str) -> bool:
        """
        在指定路径中搜索具有相同哈希值的文件

        Args:
            search_path: 搜索路径
            target_hash: 目标哈希值
            original_name: 原始文件名

        Returns:
            是否找到相同哈希值的文件
        """
        try:
            if not os.path.exists(search_path):
                return False

            # 限制搜索深度和文件数量，避免性能问题
            max_depth = 3
            max_files = 100
            searched_files = 0

            for root, dirs, files in os.walk(search_path):
                # 计算当前深度
                current_depth = os.path.relpath(root, search_path).count(os.sep) + 1
                if current_depth > max_depth:
                    continue

                for file in files:
                    if searched_files >= max_files:
                        return False

                    searched_files += 1

                    # 优先检查同名文件
                    if file == os.path.basename(original_name):
                        file_path = os.path.join(root, file)
                        try:
                            file_hash = self._calculate_file_hash(file_path)
                            if file_hash == target_hash:
                                return True
                        except:
                            continue

                    # 也检查其他文件（限制检查数量）
                    elif searched_files < 50:  # 只检查前50个不同名的文件
                        file_path = os.path.join(root, file)
                        try:
                            file_hash = self._calculate_file_hash(file_path)
                            if file_hash == target_hash:
                                return True
                        except:
                            continue

            return False

        except Exception:
            return False

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
            _logger.error(f"文件恢复失败: {e}")
            return False

    def _backup_current_state(self):
        """备份当前状态到备份目录"""
        backup_dir = os.path.join(self.workspace_path, '.verman_backup')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(backup_dir, f'backup_{timestamp}')

        try:
            os.makedirs(backup_path, exist_ok=True)

            # 扫描当前工作区文件
            current_files = self.scan_workspace()
            backed_up_count = 0

            # 复制所有文件到备份目录
            for relative_path in current_files:
                source_path = os.path.join(self.workspace_path, relative_path)
                target_path = os.path.join(backup_path, relative_path)

                # 确保目标目录存在
                target_dir = os.path.dirname(target_path)
                if target_dir:
                    os.makedirs(target_dir, exist_ok=True)

                try:
                    # 复制文件
                    import shutil
                    shutil.copy2(source_path, target_path)
                    backed_up_count += 1
                except Exception as copy_error:
                    _logger.error(f"备份文件失败 {relative_path}: {copy_error}")
                    continue

            _logger.info(f"当前状态已备份到: {backup_path}")
            _logger.info(f"共备份 {backed_up_count} 个文件")

        except Exception as e:
            _logger.error(f"备份失败: {e}")

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
            _logger.error(f"导出失败: {e}")
            return False