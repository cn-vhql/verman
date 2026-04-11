use crate::models::{
    ChangeEntry, FileRecord, SnapshotMeta, VersionBlob, VersionChangeEntry, VersionDetails,
    VersionDiffEntry, VersionDiffResult, VersionEntry, VersionStats,
};
use anyhow::{anyhow, Context, Result};
use rusqlite::{params, Connection, OptionalExtension, Transaction};
use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};
use std::time::Duration;

pub struct Repository {
    db_path: PathBuf,
}

impl Repository {
    pub fn open(workspace: &Path) -> Result<Self> {
        let repository = Self {
            db_path: workspace.join(".verman.db"),
        };
        repository.initialize(workspace)?;
        Ok(repository)
    }

    pub fn list_versions(&self) -> Result<Vec<VersionEntry>> {
        let connection = self.connect()?;
        let mut statement = connection.prepare(
            "
            SELECT id, version_number, created_at, description, change_count
            FROM versions
            ORDER BY id DESC
            ",
        )?;

        let rows = statement.query_map([], |row| {
            Ok(VersionEntry {
                id: row.get(0)?,
                version_number: row.get(1)?,
                created_at: row.get(2)?,
                description: row.get::<_, Option<String>>(3)?.unwrap_or_default(),
                change_count: row.get::<_, i64>(4)? as usize,
            })
        })?;

        rows.collect::<rusqlite::Result<Vec<_>>>()
            .map_err(Into::into)
    }

    pub fn get_version_entry(&self, version_id: i64) -> Result<VersionEntry> {
        let connection = self.connect()?;
        connection
            .query_row(
                "
                SELECT id, version_number, created_at, description, change_count
                FROM versions
                WHERE id = ?
                ",
                [version_id],
                |row| {
                    Ok(VersionEntry {
                        id: row.get(0)?,
                        version_number: row.get(1)?,
                        created_at: row.get(2)?,
                        description: row.get::<_, Option<String>>(3)?.unwrap_or_default(),
                        change_count: row.get::<_, i64>(4)? as usize,
                    })
                },
            )
            .optional()?
            .ok_or_else(|| anyhow!("Version {version_id} was not found"))
    }

    pub fn latest_snapshot(&self) -> Result<BTreeMap<String, SnapshotMeta>> {
        let connection = self.connect()?;
        let latest_version = connection
            .query_row(
                "SELECT id FROM versions ORDER BY id DESC LIMIT 1",
                [],
                |row| row.get::<_, i64>(0),
            )
            .optional()?;

        let Some(version_id) = latest_version else {
            return Ok(BTreeMap::new());
        };

        self.snapshot_for_version(version_id)
    }

    pub fn snapshot_for_version(&self, version_id: i64) -> Result<BTreeMap<String, SnapshotMeta>> {
        let connection = self.connect()?;
        let mut statement = connection.prepare(
            "
            SELECT relative_path, content_hash, size
            FROM version_files
            WHERE version_id = ?
            ORDER BY relative_path
            ",
        )?;

        let rows = statement.query_map([version_id], |row| {
            Ok((
                row.get::<_, String>(0)?,
                SnapshotMeta {
                    hash: row.get(1)?,
                    size: row.get::<_, i64>(2)? as u64,
                },
            ))
        })?;

        let mut snapshot = BTreeMap::new();
        for row in rows {
            let (path, meta) = row?;
            snapshot.insert(path, meta);
        }

        Ok(snapshot)
    }

    pub fn restore_payload(&self, version_id: i64) -> Result<Vec<VersionBlob>> {
        let connection = self.connect()?;
        let mut statement = connection.prepare(
            "
            SELECT vf.relative_path, vf.content_hash, b.content
            FROM version_files vf
            JOIN blobs b ON b.hash = vf.content_hash
            WHERE vf.version_id = ?
            ORDER BY vf.relative_path
            ",
        )?;

        let rows = statement.query_map([version_id], |row| {
            Ok(VersionBlob {
                relative_path: row.get(0)?,
                hash: row.get(1)?,
                content: row.get(2)?,
            })
        })?;

        rows.collect::<rusqlite::Result<Vec<_>>>()
            .map_err(Into::into)
    }

    pub fn create_version(
        &self,
        description: &str,
        current: &BTreeMap<String, FileRecord>,
        changes: &[ChangeEntry],
        blobs: &[VersionBlob],
    ) -> Result<()> {
        let mut connection = self.connect()?;
        let transaction = connection.transaction()?;

        let next_number = self.next_version_number(&transaction)?;
        let version_id = insert_version(&transaction, &next_number, description, changes.len())?;

        for blob in blobs {
            transaction.execute(
                "
                INSERT OR IGNORE INTO blobs (hash, size, content)
                VALUES (?, ?, ?)
                ",
                params![blob.hash, blob.content.len() as i64, blob.content],
            )?;
        }

        insert_snapshot(&transaction, version_id, current)?;
        insert_changes(&transaction, version_id, changes)?;
        transaction.commit()?;

        Ok(())
    }

    pub fn compare_versions(
        &self,
        left_version_id: i64,
        right_version_id: i64,
    ) -> Result<VersionDiffResult> {
        let left_version = self.get_version_entry(left_version_id)?;
        let right_version = self.get_version_entry(right_version_id)?;
        let left = self.snapshot_for_version(left_version_id)?;
        let right = self.snapshot_for_version(right_version_id)?;

        let all_paths: BTreeSet<_> = left.keys().chain(right.keys()).cloned().collect();

        let mut added = 0usize;
        let mut modified = 0usize;
        let mut deleted = 0usize;
        let mut entries = Vec::new();

        for path in all_paths {
            match (left.get(&path), right.get(&path)) {
                (None, Some(right_meta)) => {
                    added += 1;
                    entries.push(VersionDiffEntry {
                        relative_path: path,
                        status: "add".to_string(),
                        left_hash: None,
                        right_hash: Some(right_meta.hash.clone()),
                        left_size: None,
                        right_size: Some(right_meta.size),
                    });
                }
                (Some(left_meta), None) => {
                    deleted += 1;
                    entries.push(VersionDiffEntry {
                        relative_path: path,
                        status: "delete".to_string(),
                        left_hash: Some(left_meta.hash.clone()),
                        right_hash: None,
                        left_size: Some(left_meta.size),
                        right_size: None,
                    });
                }
                (Some(left_meta), Some(right_meta)) if left_meta.hash != right_meta.hash => {
                    modified += 1;
                    entries.push(VersionDiffEntry {
                        relative_path: path,
                        status: "modify".to_string(),
                        left_hash: Some(left_meta.hash.clone()),
                        right_hash: Some(right_meta.hash.clone()),
                        left_size: Some(left_meta.size),
                        right_size: Some(right_meta.size),
                    });
                }
                _ => {}
            }
        }

        Ok(VersionDiffResult {
            left_version_id,
            right_version_id,
            left_version_label: left_version.version_number,
            right_version_label: right_version.version_number,
            added,
            modified,
            deleted,
            entries,
        })
    }

    pub fn previous_version_entry(&self, version_id: i64) -> Result<Option<VersionEntry>> {
        let connection = self.connect()?;
        connection
            .query_row(
                "
                SELECT id, version_number, created_at, description, change_count
                FROM versions
                WHERE id < ?
                ORDER BY id DESC
                LIMIT 1
                ",
                [version_id],
                |row| {
                    Ok(VersionEntry {
                        id: row.get(0)?,
                        version_number: row.get(1)?,
                        created_at: row.get(2)?,
                        description: row.get::<_, Option<String>>(3)?.unwrap_or_default(),
                        change_count: row.get::<_, i64>(4)? as usize,
                    })
                },
            )
            .optional()
            .map_err(Into::into)
    }

    pub fn version_details(&self, version_id: i64) -> Result<VersionDetails> {
        let version = self.get_version_entry(version_id)?;
        let previous = self.previous_version_entry(version_id)?;
        let connection = self.connect()?;
        let mut statement = connection.prepare(
            "
            SELECT vc.relative_path, vc.status, vc.content_hash, COALESCE(vc.size, 0)
            FROM version_changes vc
            WHERE vc.version_id = ?
            ORDER BY
              CASE vc.status
                WHEN 'modify' THEN 0
                WHEN 'add' THEN 1
                ELSE 2
              END,
              vc.relative_path
            ",
        )?;

        let mut stats = VersionStats::default();
        let rows = statement.query_map([version_id], |row| {
            Ok((
                row.get::<_, String>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, Option<String>>(2)?,
                row.get::<_, i64>(3)? as u64,
            ))
        })?;

        let mut files = Vec::new();
        for row in rows {
            let (relative_path, status, hash, size) = row?;
            match status.as_str() {
                "add" => stats.add_count += 1,
                "modify" => stats.modify_count += 1,
                "delete" => stats.delete_count += 1,
                _ => {}
            }

            let preview_source = if status == "delete" {
                previous
                    .as_ref()
                    .and_then(|entry| self.file_bytes_for_version(entry.id, &relative_path).ok())
            } else {
                self.file_bytes_for_version(version_id, &relative_path).ok()
            };

            files.push(VersionChangeEntry {
                relative_path,
                status,
                hash,
                size,
                is_text: preview_source
                    .as_deref()
                    .map(is_probably_text)
                    .unwrap_or(false),
            });
        }

        Ok(VersionDetails {
            version,
            previous_version_label: previous.map(|entry| entry.version_number),
            stats,
            files,
        })
    }

    pub fn file_bytes_for_version(&self, version_id: i64, relative_path: &str) -> Result<Vec<u8>> {
        let connection = self.connect()?;
        connection
            .query_row(
                "
                SELECT b.content
                FROM version_files vf
                JOIN blobs b ON b.hash = vf.content_hash
                WHERE vf.version_id = ? AND vf.relative_path = ?
                ",
                params![version_id, relative_path],
                |row| row.get(0),
            )
            .optional()?
            .ok_or_else(|| anyhow!("File {relative_path} was not found in version {version_id}"))
    }

    fn initialize(&self, workspace: &Path) -> Result<()> {
        let connection = self.connect()?;
        connection.execute_batch(
            "
            CREATE TABLE IF NOT EXISTS config (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS versions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              version_number TEXT NOT NULL UNIQUE,
              created_at TEXT NOT NULL,
              description TEXT NOT NULL,
              change_count INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS blobs (
              hash TEXT PRIMARY KEY,
              size INTEGER NOT NULL,
              content BLOB NOT NULL
            );

            CREATE TABLE IF NOT EXISTS version_files (
              version_id INTEGER NOT NULL,
              relative_path TEXT NOT NULL,
              content_hash TEXT NOT NULL,
              size INTEGER NOT NULL,
              PRIMARY KEY (version_id, relative_path),
              FOREIGN KEY (version_id) REFERENCES versions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS version_changes (
              version_id INTEGER NOT NULL,
              relative_path TEXT NOT NULL,
              content_hash TEXT,
              size INTEGER,
              status TEXT NOT NULL CHECK(status IN ('add', 'modify', 'delete')),
              PRIMARY KEY (version_id, relative_path),
              FOREIGN KEY (version_id) REFERENCES versions(id) ON DELETE CASCADE
            );
            ",
        )?;

        connection.execute(
            "
            INSERT OR REPLACE INTO config (key, value)
            VALUES ('project_path', ?)
            ",
            [workspace.to_string_lossy().to_string()],
        )?;

        Ok(())
    }

    fn connect(&self) -> Result<Connection> {
        let connection = Connection::open(&self.db_path)
            .with_context(|| format!("Failed to open database {}", self.db_path.display()))?;
        connection.pragma_update(None, "foreign_keys", "ON")?;
        connection.pragma_update(None, "journal_mode", "WAL")?;
        connection.pragma_update(None, "synchronous", "NORMAL")?;
        connection.busy_timeout(Duration::from_secs(5))?;
        Ok(connection)
    }

    fn next_version_number(&self, transaction: &Transaction<'_>) -> Result<String> {
        let count: i64 =
            transaction.query_row("SELECT COUNT(*) FROM versions", [], |row| row.get(0))?;
        Ok(format!("v{:04}", count + 1))
    }
}

fn insert_version(
    transaction: &Transaction<'_>,
    version_number: &str,
    description: &str,
    change_count: usize,
) -> Result<i64> {
    let timestamp = chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string();
    transaction.execute(
        "
        INSERT INTO versions (version_number, created_at, description, change_count)
        VALUES (?, ?, ?, ?)
        ",
        params![version_number, timestamp, description, change_count as i64],
    )?;

    Ok(transaction.last_insert_rowid())
}

fn insert_snapshot(
    transaction: &Transaction<'_>,
    version_id: i64,
    current: &BTreeMap<String, FileRecord>,
) -> Result<()> {
    let mut statement = transaction.prepare(
        "
        INSERT INTO version_files (version_id, relative_path, content_hash, size)
        VALUES (?, ?, ?, ?)
        ",
    )?;

    for file in current.values() {
        statement.execute(params![
            version_id,
            file.relative_path,
            file.hash,
            file.size as i64
        ])?;
    }

    Ok(())
}

fn insert_changes(
    transaction: &Transaction<'_>,
    version_id: i64,
    changes: &[ChangeEntry],
) -> Result<()> {
    let mut statement = transaction.prepare(
        "
        INSERT INTO version_changes (version_id, relative_path, content_hash, size, status)
        VALUES (?, ?, ?, ?, ?)
        ",
    )?;

    for change in changes {
        statement.execute(params![
            version_id,
            change.relative_path,
            if change.status == "delete" {
                None::<String>
            } else {
                Some(change.hash.clone())
            },
            change.size as i64,
            change.status
        ])?;
    }

    Ok(())
}

fn is_probably_text(bytes: &[u8]) -> bool {
    if bytes.is_empty() {
        return true;
    }

    let sample = &bytes[..bytes.len().min(4096)];
    if sample.contains(&0) {
        return false;
    }

    let suspicious = sample
        .iter()
        .filter(|byte| matches!(**byte, 0x00..=0x08 | 0x0B | 0x0C | 0x0E..=0x1A | 0x1C..=0x1F))
        .count();

    suspicious * 100 <= sample.len() * 10
}
