"""
Shared models and constants for VerMan.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

DEFAULT_IGNORE_PATTERNS = [
    ".verman/",
    ".verman.db",
    ".verman.db-shm",
    ".verman.db-wal",
    ".verman.db-journal",
    ".verman.db.bak.*",
    "*.db",
    "*.db-shm",
    "*.db-wal",
    "*.db-journal",
    "*.sqlite",
    "*.sqlite3",
    ".verman_backup/",
    ".verman_temp/",
    "__pycache__/",
    "*.pyc",
    "*.pyo",
    ".git/",
    ".svn/",
    ".hg/",
    "*.tmp",
    "*.temp",
    "*.log",
    ".DS_Store",
    "Thumbs.db",
]

ACTIVE_FILE_STATUSES = {"add", "modify", "unmodified"}

CURRENT_SCHEMA_VERSION = "2"


@dataclass(frozen=True)
class FileState:
    relative_path: str
    file_hash: str
    file_size: int
    mtime_ns: int


@dataclass(frozen=True)
class BlockedFile:
    relative_path: str
    file_size: int
    reason: str


@dataclass
class ScanSnapshot:
    current_files: Dict[str, FileState]
    changes: List[Dict[str, str]]
    blocked_files: List[BlockedFile]
    scan_id: int


@dataclass
class CreateVersionResult:
    success: bool
    version_number: Optional[str] = None
    change_count: int = 0
    blocked_files: List[BlockedFile] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class RollbackResult:
    success: bool
    restored_count: int = 0
    removed_count: int = 0
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None
