"""
核心数据模型定义
"""
import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Set
from enum import Enum


class FileStatus(Enum):
    """文件状态枚举"""
    UNTRACKED = "untracked"      # 未追踪
    TRACKED = "tracked"         # 已追踪
    MODIFIED = "modified"       # 已修改
    ADDED = "added"            # 新增
    DELETED = "deleted"        # 已删除
    UNCHANGED = "unchanged"    # 未改变


@dataclass
class FileInfo:
    """文件信息数据类"""
    path: str                    # 相对于版本库根目录的路径
    hash: str                    # SHA-256 哈希值
    size: int                    # 文件大小（字节）
    mtime: float                 # 最后修改时间（时间戳）
    status: FileStatus = FileStatus.UNTRACKED  # 文件状态

    def to_dict(self) -> dict:
        """转换为字典"""
        data = asdict(self)
        data['status'] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'FileInfo':
        """从字典创建实例"""
        data['status'] = FileStatus(data['status'])
        return cls(**data)


@dataclass
class VersionInfo:
    """版本信息数据类"""
    version: int                 # 版本号
    timestamp: datetime          # 提交时间
    author: str                  # 提交者
    message: str                 # 提交信息
    added_files: List[str]       # 新增文件列表
    modified_files: List[str]    # 修改文件列表
    deleted_files: List[str]     # 删除文件列表
    parent_version: Optional[int] = None  # 父版本号

    def to_dict(self) -> dict:
        """转换为字典"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'VersionInfo':
        """从字典创建实例"""
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


@dataclass
class Config:
    """配置信息数据类"""
    author: str = os.getenv('USERNAME', os.getenv('USER', 'Unknown User'))  # 默认提交者
    ignore_file_path: str = ".svminiignore"  # 忽略文件路径

    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'Config':
        """从字典创建实例"""
        return cls(**data)


class Repository:
    """版本库核心类"""

    def __init__(self, root_path: str):
        self.root_path = os.path.abspath(root_path)
        self.svmini_path = os.path.join(self.root_path, '.svmini')
        self.config_path = os.path.join(self.svmini_path, 'config.json')
        self.index_path = os.path.join(self.svmini_path, 'index.json')
        self.versions_path = os.path.join(self.svmini_path, 'versions')
        self.backups_path = os.path.join(self.svmini_path, 'backups')

    def is_repository(self) -> bool:
        """检查当前目录是否为版本库"""
        return os.path.exists(self.svmini_path) and os.path.isdir(self.svmini_path)

    def get_file_path(self, relative_path: str) -> str:
        """获取文件的绝对路径"""
        return os.path.join(self.root_path, relative_path)

    def get_relative_path(self, file_path: str) -> str:
        """获取文件相对于版本库根目录的路径"""
        return os.path.relpath(file_path, self.root_path)

    def get_version_path(self, version: int) -> str:
        """获取版本存储路径"""
        return os.path.join(self.versions_path, str(version))

    def get_version_files_path(self, version: int) -> str:
        """获取版本文件存储路径"""
        return os.path.join(self.get_version_path(version), 'files')

    def get_version_meta_path(self, version: int) -> str:
        """获取版本元数据路径"""
        return os.path.join(self.get_version_path(version), 'meta.json')

    def get_backup_path(self, timestamp: str) -> str:
        """获取备份路径"""
        return os.path.join(self.backups_path, timestamp)


class IgnoreRules:
    """忽略规则管理类"""

    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.ignore_file_path = os.path.join(repo_path, '.svminiignore')
        self.rules: List[str] = []
        self.load_rules()

    def load_rules(self):
        """加载忽略规则"""
        if os.path.exists(self.ignore_file_path):
            with open(self.ignore_file_path, 'r', encoding='utf-8') as f:
                self.rules = [line.strip() for line in f.readlines()
                             if line.strip() and not line.startswith('#')]

    def save_rules(self):
        """保存忽略规则"""
        os.makedirs(os.path.dirname(self.ignore_file_path), exist_ok=True)
        with open(self.ignore_file_path, 'w', encoding='utf-8') as f:
            for rule in self.rules:
                f.write(rule + '\n')

    def add_rule(self, rule: str):
        """添加忽略规则"""
        if rule not in self.rules:
            self.rules.append(rule)
            self.save_rules()

    def remove_rule(self, rule: str):
        """移除忽略规则"""
        if rule in self.rules:
            self.rules.remove(rule)
            self.save_rules()

    def is_ignored(self, file_path: str) -> bool:
        """检查文件是否被忽略"""
        relative_path = os.path.relpath(file_path, self.repo_path)

        for rule in self.rules:
            if self._match_rule(relative_path, rule):
                return True
        return False

    def _match_rule(self, path: str, rule: str) -> bool:
        """检查路径是否匹配规则"""
        # 简单的通配符匹配
        if '*' in rule:
            import fnmatch
            return fnmatch.fnmatch(path, rule) or fnmatch.fnmatch(os.path.basename(path), rule)
        else:
            return path == rule or path.startswith(rule + os.sep) or os.path.basename(path) == rule