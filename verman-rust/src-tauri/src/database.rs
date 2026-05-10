use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::Mutex;

use rusqlite::{params, Connection};

use crate::models::{
    ACTIVE_FILE_STATUSES, CURRENT_SCHEMA_VERSION, FileState, VersionFileInfo, VersionInfo,
    WorkspaceIndexEntry,
};

pub struct DatabaseManager {
    conn: Mutex<Connection>,
}

#[allow(dead_code)]
impl DatabaseManager {
    pub fn new(db_path: &Path) -> Result<Self, String> {
        // Before opening an existing database, create a timestamped backup
        // to protect against data loss from WAL inconsistencies during init.
        if db_path.exists() {
            let ts = chrono::Local::now().format("%Y%m%d_%H%M%S");
            let backup_path = PathBuf::from(format!("{}.bak.{}", db_path.to_string_lossy(), ts));
            if let Err(e) = std::fs::copy(db_path, &backup_path) {
                tracing::warn!(error = %e, "Failed to backup database before open");
            } else {
                tracing::info!(backup = %backup_path.display(), "Database backed up before open");
            }
        }

        let conn = Connection::open(db_path).map_err(|e| format!("Failed to open database: {}", e))?;
        let mgr = Self { conn: Mutex::new(conn) };
        mgr.initialize()?;
        Ok(mgr)
    }

    fn initialize(&self) -> Result<(), String> {
        let conn = self.conn.lock().map_err(|e| e.to_string())?;
        conn.execute_batch("PRAGMA foreign_keys = ON").map_err(|e| e.to_string())?;
        conn.execute_batch("PRAGMA journal_mode = WAL").map_err(|e| e.to_string())?;
        conn.execute_batch("PRAGMA synchronous = NORMAL").map_err(|e| e.to_string())?;
        conn.execute_batch("PRAGMA temp_store = MEMORY").map_err(|e| e.to_string())?;

        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )",
        ).map_err(|e| e.to_string())?;

        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version_number TEXT UNIQUE NOT NULL,
                create_time TEXT NOT NULL,
                description TEXT,
                change_count INTEGER NOT NULL
            )",
        ).map_err(|e| e.to_string())?;

        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version_id INTEGER NOT NULL,
                relative_path TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                file_status TEXT NOT NULL CHECK(file_status IN ('add','modify','delete','unmodified')),
                file_content BLOB,
                FOREIGN KEY (version_id) REFERENCES versions(id) ON DELETE CASCADE,
                UNIQUE(version_id, relative_path)
            )",
        ).map_err(|e| e.to_string())?;

        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS workspace_index (
                relative_path TEXT PRIMARY KEY,
                file_hash TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                mtime_ns INTEGER NOT NULL,
                last_seen_scan_id INTEGER NOT NULL
            )",
        ).map_err(|e| e.to_string())?;

        conn.execute_batch(
            "CREATE INDEX IF NOT EXISTS idx_versions_create_time_id
                ON versions(create_time DESC, id DESC)",
        ).ok();
        conn.execute_batch(
            "CREATE INDEX IF NOT EXISTS idx_files_version_id ON files(version_id)",
        ).ok();
        conn.execute_batch(
            "CREATE INDEX IF NOT EXISTS idx_files_version_path ON files(version_id, relative_path)",
        ).ok();
        conn.execute_batch(
            "CREATE INDEX IF NOT EXISTS idx_workspace_index_relative_path
                ON workspace_index(relative_path)",
        ).ok();

        conn.execute(
            "INSERT OR REPLACE INTO config (key, value) VALUES ('schema_version', ?)",
            params![CURRENT_SCHEMA_VERSION],
        ).map_err(|e| e.to_string())?;

        Ok(())
    }

    pub fn requires_migration(db_path: &Path) -> bool {
        match Connection::open(db_path) {
            Ok(conn) => {
                let has_files = conn
                    .prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='files'")
                    .and_then(|mut stmt| stmt.exists(params![]))
                    .unwrap_or(false);
                if !has_files {
                    return true;
                }

                let has_status = conn
                    .prepare("PRAGMA table_info(files)")
                    .map(|mut stmt| {
                        let cols: Vec<String> = stmt
                            .query_map([], |row| row.get::<_, String>(1))
                            .unwrap()
                            .filter_map(|r| r.ok())
                            .collect();
                        cols.contains(&"file_status".to_string())
                    })
                    .unwrap_or(false);
                if !has_status {
                    return true;
                }

                let schema_ok = conn
                    .prepare("SELECT value FROM config WHERE key = 'schema_version'")
                    .and_then(|mut stmt| {
                        stmt.query_row([], |row| row.get::<_, String>(0))
                    })
                    .ok();
                schema_ok.as_deref() != Some(CURRENT_SCHEMA_VERSION)
            }
            Err(_) => true,
        }
    }

    // ── Config ──

    pub fn set_config(&self, key: &str, value: &str) -> Result<(), String> {
        let conn = self.conn.lock().map_err(|e| e.to_string())?;
        conn.execute(
            "INSERT OR REPLACE INTO config (key, value) VALUES (?1, ?2)",
            params![key, value],
        ).map_err(|e| e.to_string())?;
        Ok(())
    }

    pub fn get_config(&self, key: &str) -> Option<String> {
        let conn = self.conn.lock().ok()?;
        conn.query_row(
            "SELECT value FROM config WHERE key = ?1",
            params![key],
            |row| row.get(0),
        )
        .ok()
    }

    // ── Versions ──

    pub fn create_version(
        &self,
        version_number: &str,
        description: &str,
        change_count: i64,
    ) -> Result<i64, String> {
        let conn = self.conn.lock().map_err(|e| e.to_string())?;
        conn.execute(
            "INSERT INTO versions (version_number, create_time, description, change_count)
             VALUES (?1, ?2, ?3, ?4)",
            params![
                version_number,
                chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string(),
                description,
                change_count,
            ],
        ).map_err(|e| e.to_string())?;
        Ok(conn.last_insert_rowid())
    }

    pub fn get_all_versions(&self) -> Result<Vec<VersionInfo>, String> {
        let conn = self.conn.lock().map_err(|e| e.to_string())?;
        let mut stmt = conn
            .prepare(
                "SELECT id, version_number, create_time, description, change_count
                 FROM versions ORDER BY create_time DESC, id DESC",
            )
            .map_err(|e| e.to_string())?;
        let rows = stmt
            .query_map([], |row| {
                Ok(VersionInfo {
                    id: row.get(0)?,
                    version_number: row.get(1)?,
                    create_time: row.get(2)?,
                    description: row.get(3)?,
                    change_count: row.get(4)?,
                })
            })
            .map_err(|e| e.to_string())?;
        let mut versions = Vec::new();
        for row in rows {
            versions.push(row.map_err(|e| e.to_string())?);
        }
        Ok(versions)
    }

    pub fn get_latest_version_id(&self) -> Option<i64> {
        let conn = self.conn.lock().ok()?;
        conn.query_row(
            "SELECT id FROM versions ORDER BY id DESC LIMIT 1",
            [],
            |row| row.get(0),
        )
        .ok()
    }

    pub fn delete_version(&self, version_id: i64) -> Result<(), String> {
        let conn = self.conn.lock().map_err(|e| e.to_string())?;
        conn.execute("DELETE FROM versions WHERE id = ?1", params![version_id])
            .map_err(|e| e.to_string())?;
        Ok(())
    }

    // ── Files ──

    pub fn save_files(
        &self,
        version_id: i64,
        files_data: &[VersionFileInfo],
        replace_existing: bool,
    ) -> Result<(), String> {
        if files_data.is_empty() {
            return Ok(());
        }
        let conn = self.conn.lock().map_err(|e| e.to_string())?;

        let exists: bool = conn
            .query_row(
                "SELECT COUNT(*) FROM versions WHERE id = ?1",
                params![version_id],
                |row| row.get(0),
            )
            .map_err(|e| e.to_string())?;
        if !exists {
            return Err(format!("Version ID {} does not exist", version_id));
        }

        if replace_existing {
            conn.execute(
                "DELETE FROM files WHERE version_id = ?1",
                params![version_id],
            )
            .map_err(|e| e.to_string())?;
        }

        let mut stmt = conn
            .prepare(
                "INSERT INTO files (version_id, relative_path, file_hash, file_status, file_content)
                 VALUES (?1, ?2, ?3, ?4, ?5)",
            )
            .map_err(|e| e.to_string())?;

        for file in files_data {
            stmt.execute(params![
                version_id,
                file.relative_path,
                file.file_hash,
                file.file_status,
                file.file_content,
            ])
            .map_err(|e| e.to_string())?;
        }

        Ok(())
    }

    pub fn get_version_files(&self, version_id: i64) -> Result<Vec<VersionFileInfo>, String> {
        let conn = self.conn.lock().map_err(|e| e.to_string())?;
        let mut stmt = conn
            .prepare(
                "SELECT relative_path, file_hash, file_status, file_content
                 FROM files WHERE version_id = ?1 ORDER BY relative_path",
            )
            .map_err(|e| e.to_string())?;
        let rows = stmt
            .query_map(params![version_id], |row| {
                Ok(VersionFileInfo {
                    relative_path: row.get(0)?,
                    file_hash: row.get(1)?,
                    file_status: row.get(2)?,
                    file_content: row.get(3)?,
                })
            })
            .map_err(|e| e.to_string())?;
        let mut files = Vec::new();
        for row in rows {
            files.push(row.map_err(|e| e.to_string())?);
        }
        Ok(files)
    }

    pub fn get_version_file_hashes(&self, version_id: i64) -> HashMap<String, String> {
        let conn = match self.conn.lock() {
            Ok(c) => c,
            Err(_) => return HashMap::new(),
        };
        let mut stmt = match conn.prepare(
            "SELECT relative_path, file_hash, file_status
             FROM files WHERE version_id = ?1 ORDER BY relative_path",
        ) {
            Ok(s) => s,
            Err(_) => return HashMap::new(),
        };
        let rows: Vec<(String, String, String)> = stmt
            .query_map(params![version_id], |row| {
                Ok((row.get(0)?, row.get(1)?, row.get(2)?))
            })
            .ok()
            .map(|iter| iter.filter_map(|r| r.ok()).collect())
            .unwrap_or_default();

        rows.into_iter()
            .filter(|(_, _, status)| ACTIVE_FILE_STATUSES.contains(&status.as_str()))
            .map(|(path, hash, _)| (path, hash))
            .collect()
    }

    pub fn get_effective_version_files(
        &self,
        version_id: i64,
        include_content: bool,
    ) -> Result<Vec<VersionFileInfo>, String> {
        let conn = self.conn.lock().map_err(|e| e.to_string())?;

        let exists: bool = conn
            .query_row(
                "SELECT COUNT(*) FROM versions WHERE id = ?1",
                params![version_id],
                |row| row.get(0),
            )
            .map_err(|e| e.to_string())?;
        if !exists {
            return Ok(Vec::new());
        }

        let content_field = if include_content { "file_content" } else { "NULL AS file_content" };
        let sql = format!(
            "SELECT version_id, relative_path, file_hash, file_status, {}
             FROM files WHERE version_id <= ?1 ORDER BY version_id ASC, id ASC",
            content_field
        );

        let mut stmt = conn.prepare(&sql).map_err(|e| e.to_string())?;
        let rows = stmt
            .query_map(params![version_id], |row| {
                Ok((
                    row.get::<_, i64>(0)?,
                    row.get::<_, String>(1)?,
                    row.get::<_, String>(2)?,
                    row.get::<_, String>(3)?,
                    row.get::<_, Option<Vec<u8>>>(4)?,
                ))
            })
            .map_err(|e| e.to_string())?;

        let mut state: HashMap<String, VersionFileInfo> = HashMap::new();
        for row in rows {
            let (_vid, rpath, hash, status, content) = row.map_err(|e| e.to_string())?;
            let prev = state.get(&rpath).cloned();
            let effective_content = if include_content && status == "unmodified" {
                prev.and_then(|p| p.file_content).or(content)
            } else {
                content
            };

            state.insert(
                rpath.clone(),
                VersionFileInfo {
                    relative_path: rpath,
                    file_hash: hash,
                    file_status: status,
                    file_content: effective_content,
                },
            );
        }

        let mut files: Vec<VersionFileInfo> = state.into_values().collect();
        files.sort_by(|a, b| a.relative_path.cmp(&b.relative_path));
        Ok(files)
    }

    // ── Workspace Index ──

    pub fn update_workspace_index(
        &self,
        file_states: &[FileState],
        scan_id: i64,
    ) -> Result<(), String> {
        let conn = self.conn.lock().map_err(|e| e.to_string())?;

        if !file_states.is_empty() {
            let mut stmt = conn
                .prepare(
                    "INSERT INTO workspace_index
                     (relative_path, file_hash, file_size, mtime_ns, last_seen_scan_id)
                     VALUES (?1, ?2, ?3, ?4, ?5)
                     ON CONFLICT(relative_path) DO UPDATE SET
                         file_hash = excluded.file_hash,
                         file_size = excluded.file_size,
                         mtime_ns = excluded.mtime_ns,
                         last_seen_scan_id = excluded.last_seen_scan_id",
                )
                .map_err(|e| e.to_string())?;

            for fs in file_states {
                stmt.execute(params![
                    fs.relative_path,
                    fs.file_hash,
                    fs.file_size,
                    fs.mtime_ns,
                    scan_id,
                ])
                .map_err(|e| e.to_string())?;
            }

            conn.execute(
                "DELETE FROM workspace_index WHERE last_seen_scan_id != ?1",
                params![scan_id],
            )
            .map_err(|e| e.to_string())?;
        } else {
            conn.execute("DELETE FROM workspace_index", [])
                .map_err(|e| e.to_string())?;
        }

        Ok(())
    }

    pub fn get_workspace_index(&self) -> HashMap<String, WorkspaceIndexEntry> {
        let conn = match self.conn.lock() {
            Ok(c) => c,
            Err(_) => return HashMap::new(),
        };
        let mut stmt = match conn.prepare(
            "SELECT relative_path, file_hash, file_size, mtime_ns, last_seen_scan_id
             FROM workspace_index",
        ) {
            Ok(s) => s,
            Err(_) => return HashMap::new(),
        };
        let rows: Vec<(String, String, i64, i64, i64)> = stmt
            .query_map([], |row| {
                Ok((
                    row.get(0)?,
                    row.get(1)?,
                    row.get(2)?,
                    row.get(3)?,
                    row.get(4)?,
                ))
            })
            .ok()
            .map(|iter| iter.filter_map(|r| r.ok()).collect())
            .unwrap_or_default();

        rows.into_iter()
            .map(|(path, hash, size, mtime, scan_id)| {
                (
                    path,
                    WorkspaceIndexEntry {
                        file_hash: hash,
                        file_size: size,
                        mtime_ns: mtime,
                        last_seen_scan_id: scan_id,
                    },
                )
            })
            .collect()
    }

    // ── Project Info ──

    pub fn get_project_info(&self) -> Option<(String, String)> {
        let path = self.get_config("project_path")?;
        let time = self.get_config("create_time").unwrap_or_default();
        Some((path, time))
    }
}

impl Drop for DatabaseManager {
    fn drop(&mut self) {
        // Connection closes automatically when dropped
    }
}
