"""
SQLite database management for VerMan.
"""

import sqlite3
import threading
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from logger import logger as app_logger
from models import ACTIVE_FILE_STATUSES, CURRENT_SCHEMA_VERSION, FileState


class DatabaseManager:
    """Database access layer for versions, files, config, and workspace index."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._db_lock = threading.RLock()
        self._initialize_database()

    @staticmethod
    def requires_migration(db_path: str) -> bool:
        """Check whether an existing database needs a schema upgrade."""
        try:
            conn = sqlite3.connect(db_path)
            try:
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
                tables = {row[0] for row in cursor.fetchall()}
                if "workspace_index" not in tables or "config" not in tables:
                    return True

                cursor = conn.execute("PRAGMA table_info(files)")
                columns = [row[1] for row in cursor.fetchall()]
                if "file_status" not in columns:
                    return True

                cursor = conn.execute(
                    "SELECT value FROM config WHERE key = 'schema_version'"
                )
                row = cursor.fetchone()
                return row is None or row[0] != CURRENT_SCHEMA_VERSION
            finally:
                conn.close()
        except sqlite3.DatabaseError:
            return True

    def _initialize_database(self):
        try:
            with self._db_lock:
                self.conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30)
                self._configure_connection()
                self._create_core_tables()
                self._migrate_database()
                self._create_auxiliary_tables()
                self._create_indexes()
                self._set_schema_version()
        except Exception as exc:
            raise Exception(f"数据库初始化失败: {exc}")

    def _configure_connection(self):
        pragmas = [
            "PRAGMA foreign_keys = ON",
            "PRAGMA journal_mode = WAL",
            "PRAGMA synchronous = NORMAL",
            "PRAGMA temp_store = MEMORY",
        ]
        for statement in pragmas:
            self.conn.execute(statement)

    def _create_core_tables(self):
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version_number TEXT UNIQUE NOT NULL,
                create_time TEXT NOT NULL,
                description TEXT,
                change_count INTEGER NOT NULL
            )
            """
        )

        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version_id INTEGER NOT NULL,
                relative_path TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                file_status TEXT NOT NULL
                    CHECK(file_status IN ('add', 'modify', 'delete', 'unmodified')),
                file_content BLOB,
                FOREIGN KEY (version_id) REFERENCES versions(id) ON DELETE CASCADE,
                UNIQUE(version_id, relative_path)
            )
            """
        )
        self.conn.commit()

    def _migrate_database(self):
        try:
            cursor = self.conn.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='files'
                """
            )
            if cursor.fetchone() is None:
                return

            cursor = self.conn.execute("PRAGMA table_info(files)")
            columns = [row[1] for row in cursor.fetchall()]
            if "file_status" not in columns:
                self._migrate_files_table()
        except Exception as exc:
            app_logger.warning(f"数据库迁移警告: {exc}")

    def _create_auxiliary_tables(self):
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace_index (
                relative_path TEXT PRIMARY KEY,
                file_hash TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                mtime_ns INTEGER NOT NULL,
                last_seen_scan_id INTEGER NOT NULL
            )
            """
        )
        self.conn.commit()

    def _create_indexes(self):
        statements = [
            "CREATE INDEX IF NOT EXISTS idx_versions_create_time_id ON versions(create_time DESC, id DESC)",
            "CREATE INDEX IF NOT EXISTS idx_files_version_id ON files(version_id)",
            "CREATE INDEX IF NOT EXISTS idx_files_version_path ON files(version_id, relative_path)",
            "CREATE INDEX IF NOT EXISTS idx_workspace_index_relative_path ON workspace_index(relative_path)",
        ]
        for statement in statements:
            self.conn.execute(statement)
        self.conn.commit()

    def _set_schema_version(self):
        self.conn.execute(
            "INSERT OR REPLACE INTO config (key, value) VALUES ('schema_version', ?)",
            (CURRENT_SCHEMA_VERSION,),
        )
        self.conn.commit()

    def _migrate_files_table(self):
        """Safely rebuild the files table while preserving existing data."""
        try:
            self.conn.execute("BEGIN TRANSACTION")

            cursor = self.conn.execute("SELECT * FROM files")
            existing_data = cursor.fetchall()

            cursor = self.conn.execute("PRAGMA table_info(files)")
            old_columns = [col[1] for col in cursor.fetchall()]
            status_index = old_columns.index("file_status") if "file_status" in old_columns else -1
            content_index = old_columns.index("file_content") if "file_content" in old_columns else -1

            self.conn.execute("DROP TABLE files")
            self.conn.execute(
                """
                CREATE TABLE files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version_id INTEGER NOT NULL,
                    relative_path TEXT NOT NULL,
                    file_hash TEXT NOT NULL,
                    file_status TEXT NOT NULL
                        CHECK(file_status IN ('add', 'modify', 'delete', 'unmodified')),
                    file_content BLOB,
                    FOREIGN KEY (version_id) REFERENCES versions(id) ON DELETE CASCADE,
                    UNIQUE(version_id, relative_path)
                )
                """
            )

            for row in existing_data:
                version_id = row[1]
                relative_path = row[2]
                file_hash = row[3]
                if status_index >= 0 and row[status_index]:
                    file_status = row[status_index]
                else:
                    # Legacy databases stored full snapshots without file_status.
                    # Treat them as active rows with embedded content so rollback
                    # and export can still reconstruct historical versions.
                    file_status = "add"
                file_content = row[content_index] if content_index >= 0 else None
                self.conn.execute(
                    """
                    INSERT INTO files
                    (version_id, relative_path, file_hash, file_status, file_content)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        version_id,
                        relative_path,
                        file_hash,
                        file_status or "unmodified",
                        file_content,
                    ),
                )

            self.conn.commit()
            app_logger.info(f"成功迁移 files 表，恢复了 {len(existing_data)} 条记录")
        except Exception as exc:
            self.conn.rollback()
            app_logger.error(f"数据库迁移失败: {exc}")
            raise

    def set_config(self, key: str, value: str):
        with self._db_lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
                (key, value),
            )
            self.conn.commit()

    def get_config(self, key: str) -> Optional[str]:
        with self._db_lock:
            cursor = self.conn.execute("SELECT value FROM config WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else None

    def create_version(self, version_number: str, description: str, change_count: int) -> int:
        with self._db_lock:
            cursor = self.conn.execute(
                """
                INSERT INTO versions (version_number, create_time, description, change_count)
                VALUES (?, ?, ?, ?)
                """,
                (
                    version_number,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    description,
                    change_count,
                ),
            )
            version_id = cursor.lastrowid
            self.conn.commit()
            return version_id

    def get_all_versions(self) -> List[Dict]:
        with self._db_lock:
            cursor = self.conn.execute(
                """
                SELECT id, version_number, create_time, description, change_count
                FROM versions
                ORDER BY create_time DESC, id DESC
                """
            )
            return [
                {
                    "id": row[0],
                    "version_number": row[1],
                    "create_time": row[2],
                    "description": row[3],
                    "change_count": row[4],
                }
                for row in cursor.fetchall()
            ]

    def save_files(self, version_id: int, files_data: List[Dict], replace_existing: bool = True):
        if not files_data:
            return

        try:
            with self._db_lock:
                self.conn.execute("BEGIN TRANSACTION")

                cursor = self.conn.execute("SELECT id FROM versions WHERE id = ?", (version_id,))
                if not cursor.fetchone():
                    raise ValueError(f"版本 ID {version_id} 不存在")

                if replace_existing:
                    self.conn.execute("DELETE FROM files WHERE version_id = ?", (version_id,))

                rows_to_insert = []
                for file_data in files_data:
                    for field in ("relative_path", "file_hash", "file_status"):
                        if field not in file_data or file_data[field] is None:
                            raise ValueError(f"文件数据缺少必要字段: {field}")

                    rows_to_insert.append(
                        (
                            version_id,
                            file_data["relative_path"],
                            file_data["file_hash"],
                            file_data["file_status"],
                            file_data.get("file_content"),
                        )
                    )

                self.conn.executemany(
                    """
                    INSERT INTO files
                    (version_id, relative_path, file_hash, file_status, file_content)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    rows_to_insert,
                )
                self.conn.commit()
        except Exception as exc:
            with self._db_lock:
                self.conn.rollback()
            raise Exception(f"保存文件数据失败: {exc}")

    def get_version_files(self, version_id: int) -> List[Dict]:
        with self._db_lock:
            cursor = self.conn.execute(
                """
                SELECT relative_path, file_hash, file_status, file_content
                FROM files
                WHERE version_id = ?
                ORDER BY relative_path
                """,
                (version_id,),
            )
            return [
                {
                    "relative_path": row[0],
                    "file_hash": row[1],
                    "file_status": row[2],
                    "file_content": row[3],
                }
                for row in cursor.fetchall()
            ]

    def get_version_file_hashes(self, version_id: int) -> Dict[str, str]:
        with self._db_lock:
            cursor = self.conn.execute(
                """
                SELECT relative_path, file_hash, file_status
                FROM files
                WHERE version_id = ?
                ORDER BY relative_path
                """,
                (version_id,),
            )
            return {
                row[0]: row[1]
                for row in cursor.fetchall()
                if row[2] in ACTIVE_FILE_STATUSES
            }

    def get_effective_version_files(
        self, version_id: int, include_content: bool = True
    ) -> List[Dict]:
        """
        Rebuild the target version state, carrying forward file content for
        `unmodified` rows so rollback/export can reconstruct complete snapshots.
        """
        select_content = "file_content" if include_content else "NULL AS file_content"
        with self._db_lock:
            cursor = self.conn.execute("SELECT id FROM versions WHERE id = ?", (version_id,))
            if not cursor.fetchone():
                return []

            cursor = self.conn.execute(
                f"""
                SELECT version_id, relative_path, file_hash, file_status, {select_content}
                FROM files
                WHERE version_id <= ?
                ORDER BY version_id ASC, id ASC
                """,
                (version_id,),
            )

            state: Dict[str, Dict] = {}
            for _, relative_path, file_hash, file_status, file_content in cursor.fetchall():
                previous = state.get(relative_path)
                if include_content and file_status == "unmodified":
                    file_content = previous.get("file_content") if previous else file_content

                state[relative_path] = {
                    "relative_path": relative_path,
                    "file_hash": file_hash,
                    "file_status": file_status,
                    "file_content": file_content if include_content else None,
                }

            return [state[path] for path in sorted(state.keys())]

    def get_latest_version_id(self) -> Optional[int]:
        with self._db_lock:
            cursor = self.conn.execute("SELECT id FROM versions ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            return row[0] if row else None

    def update_workspace_index(self, file_states: Iterable[FileState], scan_id: int):
        rows = [
            (
                state.relative_path,
                state.file_hash,
                state.file_size,
                state.mtime_ns,
                scan_id,
            )
            for state in file_states
        ]

        with self._db_lock:
            self.conn.execute("BEGIN TRANSACTION")
            if rows:
                self.conn.executemany(
                    """
                    INSERT INTO workspace_index
                    (relative_path, file_hash, file_size, mtime_ns, last_seen_scan_id)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(relative_path) DO UPDATE SET
                        file_hash = excluded.file_hash,
                        file_size = excluded.file_size,
                        mtime_ns = excluded.mtime_ns,
                        last_seen_scan_id = excluded.last_seen_scan_id
                    """,
                    rows,
                )
                self.conn.execute(
                    "DELETE FROM workspace_index WHERE last_seen_scan_id != ?",
                    (scan_id,),
                )
            else:
                self.conn.execute("DELETE FROM workspace_index")
            self.conn.commit()

    def get_workspace_index(self) -> Dict[str, Dict[str, int]]:
        with self._db_lock:
            cursor = self.conn.execute(
                """
                SELECT relative_path, file_hash, file_size, mtime_ns, last_seen_scan_id
                FROM workspace_index
                """
            )
            return {
                row[0]: {
                    "file_hash": row[1],
                    "file_size": row[2],
                    "mtime_ns": row[3],
                    "last_seen_scan_id": row[4],
                }
                for row in cursor.fetchall()
            }

    def delete_version(self, version_id: int):
        with self._db_lock:
            self.conn.execute("DELETE FROM versions WHERE id = ?", (version_id,))
            self.conn.commit()

    def close(self):
        with self._db_lock:
            if self.conn:
                self.conn.close()
                self.conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
