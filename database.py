"""
SQLite数据库管理模块
负责创建和管理项目数据库，包含三个核心表：
- config: 项目配置信息
- versions: 版本信息
- files: 文件快照
"""

import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import json

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


class DatabaseManager:
    """数据库管理器，负责所有数据库操作"""

    def __init__(self, db_path: str):
        """
        初始化数据库管理器

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._initialize_database()

    def _initialize_database(self):
        """初始化数据库，创建必要的表"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.execute("PRAGMA foreign_keys = ON")
            self._migrate_database()
            self._create_tables()
        except Exception as e:
            raise Exception(f"数据库初始化失败: {e}")

    def _migrate_database(self):
        """安全地迁移数据库，检查并更新表结构"""
        try:
            # 检查files表是否存在
            cursor = self.conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='files'
            """)
            table_exists = cursor.fetchone() is not None

            if table_exists:
                # 检查表结构是否需要更新
                cursor = self.conn.execute("PRAGMA table_info(files)")
                columns = [row[1] for row in cursor.fetchall()]

                # 检查是否有file_status列和正确的约束
                if 'file_status' not in columns:
                    # 安全迁移：备份数据，创建新表，恢复数据
                    self._migrate_files_table()
                else:
                    # 检查约束是否正确
                    cursor = self.conn.execute("""
                        SELECT sql FROM sqlite_master
                        WHERE type='table' AND name='files'
                    """)
                    create_sql = cursor.fetchone()[0]

                    if "file_status IN ('add', 'modify', 'delete', 'unmodified')" not in create_sql:
                        self._migrate_files_table()

        except Exception as e:
            # 不删除数据，记录错误但继续
            _logger.warning(f"数据库迁移警告: {e}")
            pass

    def _create_tables(self):
        """创建三个核心表"""

        # 配置表 - 存储项目基础信息
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')

        # 版本表 - 存储版本元数据
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version_number TEXT UNIQUE NOT NULL,
                create_time TEXT NOT NULL,
                description TEXT,
                change_count INTEGER NOT NULL
            )
        ''')

        # 文件表 - 存储文件快照
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version_id INTEGER NOT NULL,
                relative_path TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                file_status TEXT NOT NULL CHECK(file_status IN ('add', 'modify', 'delete', 'unmodified')),
                file_content BLOB,
                FOREIGN KEY (version_id) REFERENCES versions(id) ON DELETE CASCADE,
                UNIQUE(version_id, relative_path)
            )
        ''')

        self.conn.commit()

    def _migrate_files_table(self):
        """安全地迁移files表结构，保留所有现有数据"""
        try:
            # 开始事务
            self.conn.execute("BEGIN TRANSACTION")

            # 1. 备份现有数据
            cursor = self.conn.execute("SELECT * FROM files")
            existing_data = cursor.fetchall()

            # 2. 获取列信息
            cursor = self.conn.execute("PRAGMA table_info(files)")
            columns_info = cursor.fetchall()
            old_columns = [col[1] for col in columns_info]

            # 3. 删除旧表
            self.conn.execute("DROP TABLE files")

            # 4. 创建新表（通过_create_tables会重新创建）
            self.conn.execute('''
                CREATE TABLE files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version_id INTEGER NOT NULL,
                    relative_path TEXT NOT NULL,
                    file_hash TEXT NOT NULL,
                    file_status TEXT NOT NULL CHECK(file_status IN ('add', 'modify', 'delete', 'unmodified')),
                    file_content BLOB,
                    FOREIGN KEY (version_id) REFERENCES versions(id) ON DELETE CASCADE,
                    UNIQUE(version_id, relative_path)
                )
            ''')

            # 5. 恢复数据
            if existing_data and len(old_columns) >= 4:  # 至少需要基本列
                # 适配列名
                column_mapping = {
                    0: 'id', 1: 'version_id', 2: 'relative_path', 3: 'file_hash'
                }

                # 如果有file_status列，使用它；否则默认为'unmodified'
                if 'file_status' in old_columns:
                    status_index = old_columns.index('file_status')
                else:
                    status_index = -1

                # 如果有file_content列，使用它；否则为NULL
                if 'file_content' in old_columns:
                    content_index = old_columns.index('file_content')
                else:
                    content_index = -1

                # 逐行恢复数据
                for row in existing_data:
                    try:
                        # 获取基础数据
                        version_id = row[1]
                        relative_path = row[2]
                        file_hash = row[3]

                        # 确定状态
                        if status_index >= 0:
                            file_status = row[status_index] or 'unmodified'
                        else:
                            file_status = 'unmodified'

                        # 确定内容
                        if content_index >= 0 and content_index < len(row):
                            file_content = row[content_index]
                        else:
                            file_content = None

                        # 插入数据
                        self.conn.execute('''
                            INSERT INTO files
                            (version_id, relative_path, file_hash, file_status, file_content)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (version_id, relative_path, file_hash, file_status, file_content))

                    except Exception as row_error:
                        print(f"恢复数据行时出错: {row_error}")
                        continue

            # 提交事务
            self.conn.commit()
            _logger.info(f"成功迁移files表，恢复了 {len(existing_data)} 条记录")

        except Exception as e:
            # 回滚事务
            self.conn.rollback()
            _logger.error(f"数据库迁移失败: {e}")
            raise

    def set_config(self, key: str, value: str):
        """设置配置项"""
        self.conn.execute('''
            INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)
        ''', (key, value))
        self.conn.commit()

    def get_config(self, key: str) -> Optional[str]:
        """获取配置项"""
        cursor = self.conn.execute('SELECT value FROM config WHERE key = ?', (key,))
        row = cursor.fetchone()
        return row[0] if row else None

    def create_version(self, version_number: str, description: str, change_count: int) -> int:
        """创建新版本，返回版本ID"""
        cursor = self.conn.execute('''
            INSERT INTO versions (version_number, create_time, description, change_count)
            VALUES (?, ?, ?, ?)
        ''', (version_number, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), description, change_count))

        version_id = cursor.lastrowid
        self.conn.commit()
        return version_id

    def get_all_versions(self) -> List[Dict]:
        """获取所有版本信息"""
        cursor = self.conn.execute('''
            SELECT id, version_number, create_time, description, change_count
            FROM versions
            ORDER BY create_time DESC
        ''')

        return [{
            'id': row[0],
            'version_number': row[1],
            'create_time': row[2],
            'description': row[3],
            'change_count': row[4]
        } for row in cursor.fetchall()]

    def save_files(self, version_id: int, files_data: List[Dict]):
        """批量保存文件快照，使用事务保证数据完整性"""
        if not files_data:
            return

        try:
            # 开始事务
            self.conn.execute("BEGIN TRANSACTION")

            # 验证版本ID是否存在
            cursor = self.conn.execute("SELECT id FROM versions WHERE id = ?", (version_id,))
            if not cursor.fetchone():
                raise ValueError(f"版本ID {version_id} 不存在")

            # 批量删除现有记录（如果有的话）
            self.conn.execute("DELETE FROM files WHERE version_id = ?", (version_id,))

            # 批量插入新记录
            for file_data in files_data:
                # 数据验证
                required_fields = ['relative_path', 'file_hash', 'file_status']
                for field in required_fields:
                    if field not in file_data or file_data[field] is None:
                        raise ValueError(f"文件数据缺少必要字段: {field}")

                # 验证状态值
                if file_data['file_status'] not in ['add', 'modify', 'delete', 'unmodified']:
                    raise ValueError(f"无效的文件状态: {file_data['file_status']}")

                self.conn.execute('''
                    INSERT INTO files
                    (version_id, relative_path, file_hash, file_status, file_content)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    version_id,
                    file_data['relative_path'],
                    file_data['file_hash'],
                    file_data['file_status'],
                    file_data.get('file_content')
                ))

            # 提交事务
            self.conn.commit()

        except Exception as e:
            # 回滚事务
            try:
                self.conn.rollback()
            except:
                pass
            raise Exception(f"保存文件数据失败: {e}")

    def get_version_files(self, version_id: int) -> List[Dict]:
        """获取指定版本的所有文件"""
        cursor = self.conn.execute('''
            SELECT relative_path, file_hash, file_status, file_content
            FROM files
            WHERE version_id = ?
            ORDER BY relative_path
        ''', (version_id,))

        return [{
            'relative_path': row[0],
            'file_hash': row[1],
            'file_status': row[2],
            'file_content': row[3]
        } for row in cursor.fetchall()]

    def get_latest_version_id(self) -> Optional[int]:
        """获取最新版本的ID"""
        cursor = self.conn.execute('SELECT id FROM versions ORDER BY id DESC LIMIT 1')
        row = cursor.fetchone()
        return row[0] if row else None

    def delete_version(self, version_id: int):
        """删除版本（级联删除相关文件记录）"""
        self.conn.execute('DELETE FROM versions WHERE id = ?', (version_id,))
        self.conn.commit()

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()