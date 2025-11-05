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
        """强制使用新模式，删除旧表并创建支持完整状态的新表"""
        try:
            # 检查files表是否存在
            cursor = self.conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='files'
            """)
            table_exists = cursor.fetchone() is not None

            if table_exists:
                # 直接删除旧表，确保使用新的表结构
                self.conn.execute("DROP TABLE files")

        except Exception as e:
            # 确保删除可能损坏的表
            try:
                self.conn.execute("DROP TABLE IF EXISTS files")
            except:
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
        """批量保存文件快照"""
        for file_data in files_data:
            self.conn.execute('''
                INSERT OR REPLACE INTO files
                (version_id, relative_path, file_hash, file_status, file_content)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                version_id,
                file_data['relative_path'],
                file_data['file_hash'],
                file_data['file_status'],
                file_data.get('file_content')
            ))

        self.conn.commit()

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