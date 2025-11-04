"""
SVNLite - 轻量级本地文件版本管理系统
"""

__version__ = "0.1.0"
__author__ = "SVNLite Team"
__email__ = "support@svnlite.com"

from .core.models import Repository, FileInfo, VersionInfo, FileStatus, Config
from .core.repository_manager import RepositoryManager
from .core.file_tracker import FileTracker
from .core.commit_manager import CommitManager
from .core.diff_manager import DiffManager
from .core.rollback_manager import RollbackManager
from .core.backup_manager import BackupManager

__all__ = [
    'Repository',
    'FileInfo',
    'VersionInfo',
    'FileStatus',
    'Config',
    'RepositoryManager',
    'FileTracker',
    'CommitManager',
    'DiffManager',
    'RollbackManager',
    'BackupManager'
]