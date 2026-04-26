"""Canonical workspace metadata paths for VerMan projects."""

from __future__ import annotations

import os
from typing import Iterator, Optional


VERMAN_DIR_NAME = ".verman"
PROJECT_DB_FILENAME = "project.db"
IGNORE_FILENAME = ".vermanignore"
BACKUP_DIR_NAME = "backup"

LEGACY_DB_FILENAME = ".verman.db"
LEGACY_BACKUP_DIR_NAME = ".verman_backup"
DATABASE_SIDE_SUFFIXES = ("", "-wal", "-shm", "-journal")


def normalize_workspace_path(workspace_path: str) -> str:
    return os.path.abspath(workspace_path)


def get_metadata_dir(workspace_path: str) -> str:
    return os.path.join(normalize_workspace_path(workspace_path), VERMAN_DIR_NAME)


def ensure_metadata_dir(workspace_path: str) -> str:
    metadata_dir = get_metadata_dir(workspace_path)
    os.makedirs(metadata_dir, exist_ok=True)
    return metadata_dir


def get_project_database_path(workspace_path: str) -> str:
    return os.path.join(get_metadata_dir(workspace_path), PROJECT_DB_FILENAME)


def get_ignore_file_path(workspace_path: str) -> str:
    return os.path.join(normalize_workspace_path(workspace_path), IGNORE_FILENAME)


def get_backup_dir(workspace_path: str) -> str:
    return os.path.join(get_metadata_dir(workspace_path), BACKUP_DIR_NAME)


def get_legacy_database_path(workspace_path: str) -> str:
    return os.path.join(normalize_workspace_path(workspace_path), LEGACY_DB_FILENAME)


def get_legacy_backup_dir(workspace_path: str) -> str:
    return os.path.join(normalize_workspace_path(workspace_path), LEGACY_BACKUP_DIR_NAME)


def iter_database_sidecar_paths(database_path: str) -> Iterator[str]:
    for suffix in DATABASE_SIDE_SUFFIXES:
        yield f"{database_path}{suffix}"


def find_existing_database_path(workspace_path: str) -> Optional[str]:
    database_path = get_project_database_path(workspace_path)
    if os.path.exists(database_path):
        return database_path

    legacy_database_path = get_legacy_database_path(workspace_path)
    if os.path.exists(legacy_database_path):
        return legacy_database_path

    return None


def is_project_workspace(workspace_path: str) -> bool:
    return find_existing_database_path(workspace_path) is not None
