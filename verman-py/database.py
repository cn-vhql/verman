"""
SQLite database management for VerMan.
"""

import logging
import sqlite3
import threading
from datetime import datetime
from typing import Dict, List, Optional


class _SimpleLogger:
    """Minimal logger wrapper used across the project."""

    def __init__(self):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def info(self, msg):
        self.logger.info(msg)

    def error(self, msg):
        self.logger.error(msg)

    def warning(self, msg):
        self.logger.warning(msg)

    def debug(self, msg):
        self.logger.debug(msg)


_logger = _SimpleLogger()


class DatabaseManager:
    """Database access layer for versions, files, and config."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._db_lock = threading.RLock()
        self._initialize_database()

    def _initialize_database(self):
        try:
            with self._db_lock:
                self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
                self.conn.execute("PRAGMA foreign_keys = ON")
                self._migrate_database()
                self._create_tables()
        except Exception as e:
            raise Exception(f"数据库初始化失败: {e}")

    def _migrate_database(self):
        """Ensure the files table has the expected schema."""
        try:
            cursor = self.conn.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='files'
                """
            )
            table_exists = cursor.fetchone() is not None
            if not table_exists:
                return

            cursor = self.conn.execute("PRAGMA table_info(files)")
            columns = [row[1] for row in cursor.fetchall()]
            if "file_status" not in columns:
                self._migrate_files_table()
                return

            cursor = self.conn.execute(
                """
                SELECT sql FROM sqlite_master
                WHERE type='table' AND name='files'
                """
            )
            create_sql = cursor.fetchone()[0]
            if "file_status IN ('add', 'modify', 'delete', 'unmodified')" not in create_sql:
                self._migrate_files_table()
        except Exception as e:
            _logger.warning(f"数据库迁移警告: {e}")

    def _create_tables(self):
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
                try:
                    version_id = row[1]
                    relative_path = row[2]
                    file_hash = row[3]
                    file_status = row[status_index] if status_index >= 0 else "unmodified"
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
                except Exception as row_error:
                    _logger.warning(f"迁移单行文件记录失败: {row_error}")

            self.conn.commit()
            _logger.info(f"成功迁移 files 表，恢复了 {len(existing_data)} 条记录")
        except Exception as e:
            self.conn.rollback()
            _logger.error(f"数据库迁移失败: {e}")
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

                    if file_data["file_status"] not in {"add", "modify", "delete", "unmodified"}:
                        raise ValueError(f"无效的文件状态: {file_data['file_status']}")

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
        except Exception as e:
            try:
                with self._db_lock:
                    self.conn.rollback()
            except Exception:
                pass
            raise Exception(f"保存文件数据失败: {e}")

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

    def get_effective_version_files(self, version_id: int) -> List[Dict]:
        """
        Rebuild the target version state, carrying forward file content for
        `unmodified` rows so rollback/export can reconstruct complete snapshots.
        """
        with self._db_lock:
            cursor = self.conn.execute("SELECT id FROM versions WHERE id = ?", (version_id,))
            if not cursor.fetchone():
                return []

            cursor = self.conn.execute(
                """
                SELECT version_id, relative_path, file_hash, file_status, file_content
                FROM files
                WHERE version_id <= ?
                ORDER BY version_id ASC, id ASC
                """,
                (version_id,),
            )

            state: Dict[str, Dict] = {}
            for row in cursor.fetchall():
                _, relative_path, file_hash, file_status, file_content = row
                previous = state.get(relative_path)
                if file_status == "unmodified":
                    file_content = previous.get("file_content") if previous else None

                state[relative_path] = {
                    "relative_path": relative_path,
                    "file_hash": file_hash,
                    "file_status": file_status,
                    "file_content": file_content,
                }

            return [state[path] for path in sorted(state.keys())]

    def get_latest_version_id(self) -> Optional[int]:
        with self._db_lock:
            cursor = self.conn.execute("SELECT id FROM versions ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            return row[0] if row else None

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
