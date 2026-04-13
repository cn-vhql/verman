use anyhow::{Context, Result, anyhow};
use chrono::{DateTime, Utc};
use rusqlite::{Connection, OptionalExtension, params};
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::Path;
use verman_core::{
    AppSettings, ChangeStatus, SnapshotFileEntry, VersionChangeEntry, VersionDetails,
    VersionDiffEntry, VersionDiffResult, VersionEntry, VersionFilePreview, VersionStats,
};

pub struct Repository {
    conn: Connection,
}

#[derive(Clone, Debug)]
pub struct SnapshotFileInput {
    pub relative_path: String,
    pub hash: String,
    pub size: u64,
    pub content: Vec<u8>,
}

pub struct SnapshotInput {
    pub workspace_path: String,
    pub fingerprint: String,
    pub description: String,
    pub files: Vec<SnapshotFileInput>,
}

impl Repository {
    pub fn open_in_memory() -> Result<Self> {
        let conn = Connection::open_in_memory()?;
        let repo = Self { conn };
        repo.init_schema()?;
        Ok(repo)
    }

    pub fn open_or_create(path: &Path) -> Result<Self> {
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent).with_context(|| {
                format!("failed to create repository directory {}", parent.display())
            })?;
        }

        let conn = Connection::open(path)
            .with_context(|| format!("failed to open repository {}", path.display()))?;
        let repo = Self { conn };
        repo.init_schema()?;
        Ok(repo)
    }

    pub fn load_settings(&self) -> Result<AppSettings> {
        let mut settings = AppSettings::default();
        if let Some(language) = self
            .conn
            .query_row(
                "SELECT value FROM app_settings WHERE key = 'language'",
                [],
                |row| row.get::<_, String>(0),
            )
            .optional()?
        {
            settings.language = language;
        }

        if let Some(raw_backup) = self
            .conn
            .query_row(
                "SELECT value FROM app_settings WHERE key = 'backup_before_restore'",
                [],
                |row| row.get::<_, String>(0),
            )
            .optional()?
        {
            settings.backup_before_restore = raw_backup == "1";
        }

        Ok(settings)
    }

    pub fn save_settings(&self, settings: &AppSettings) -> Result<()> {
        self.conn.execute(
            "INSERT INTO app_settings (key, value) VALUES ('language', ?1)
             ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            params![settings.language],
        )?;
        self.conn.execute(
            "INSERT INTO app_settings (key, value) VALUES ('backup_before_restore', ?1)
             ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            params![if settings.backup_before_restore {
                "1"
            } else {
                "0"
            }],
        )?;
        Ok(())
    }

    pub fn latest_snapshot_files(&self, workspace_path: &str) -> Result<Vec<SnapshotFileEntry>> {
        let Some(snapshot_id) = self.latest_snapshot_id(workspace_path)? else {
            return Ok(Vec::new());
        };
        self.snapshot_files(snapshot_id)
    }

    pub fn create_version(&mut self, input: SnapshotInput) -> Result<Option<VersionEntry>> {
        let latest_fingerprint = self.latest_fingerprint(&input.workspace_path)?;
        if latest_fingerprint.as_deref() == Some(input.fingerprint.as_str()) {
            return Ok(None);
        }

        let tx = self.conn.transaction()?;
        let created_at = Utc::now();
        let next_index: i64 = tx.query_row(
            "SELECT COALESCE(MAX(snapshot_index), 0) + 1
             FROM snapshots
             WHERE workspace_path = ?1",
            params![input.workspace_path],
            |row| row.get(0),
        )?;
        let version_number = format!("v{next_index:04}");
        let change_count = input.files.len();

        tx.execute(
            "INSERT INTO snapshots (
                workspace_path,
                snapshot_index,
                version_number,
                description,
                fingerprint,
                created_at,
                file_count
            ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)",
            params![
                input.workspace_path,
                next_index,
                version_number,
                input.description,
                input.fingerprint,
                created_at.to_rfc3339(),
                change_count as i64
            ],
        )?;

        let snapshot_id = tx.last_insert_rowid();
        for file in &input.files {
            tx.execute(
                "INSERT INTO snapshot_files (
                    snapshot_id,
                    relative_path,
                    hash,
                    size_bytes,
                    content
                ) VALUES (?1, ?2, ?3, ?4, ?5)",
                params![
                    snapshot_id,
                    file.relative_path,
                    file.hash,
                    file.size as i64,
                    file.content
                ],
            )?;
        }

        tx.commit()?;

        Ok(Some(VersionEntry {
            id: snapshot_id,
            version_number,
            created_at,
            description: input.description,
            change_count,
        }))
    }

    pub fn list_versions(&self, workspace_path: &str, limit: usize) -> Result<Vec<VersionEntry>> {
        let mut statement = self.conn.prepare(
            "SELECT id, version_number, description, created_at, file_count
             FROM snapshots
             WHERE workspace_path = ?1
             ORDER BY id DESC
             LIMIT ?2",
        )?;

        let rows = statement.query_map(params![workspace_path, limit as i64], |row| {
            let created_at_raw: String = row.get(3)?;
            let created_at = DateTime::parse_from_rfc3339(&created_at_raw)
                .map(|value| value.with_timezone(&Utc))
                .map_err(|error| {
                    rusqlite::Error::FromSqlConversionFailure(
                        3,
                        rusqlite::types::Type::Text,
                        Box::new(error),
                    )
                })?;

            Ok(VersionEntry {
                id: row.get(0)?,
                version_number: row.get(1)?,
                description: row.get(2)?,
                created_at,
                change_count: row.get::<_, i64>(4)? as usize,
            })
        })?;

        let mut versions = Vec::new();
        for row in rows {
            versions.push(row?);
        }
        Ok(versions)
    }

    pub fn get_version(&self, version_id: i64) -> Result<VersionEntry> {
        self.conn
            .query_row(
                "SELECT id, version_number, description, created_at, file_count
                 FROM snapshots
                 WHERE id = ?1",
                params![version_id],
                |row| {
                    let created_at_raw: String = row.get(3)?;
                    let created_at = DateTime::parse_from_rfc3339(&created_at_raw)
                        .map(|value| value.with_timezone(&Utc))
                        .map_err(|error| {
                            rusqlite::Error::FromSqlConversionFailure(
                                3,
                                rusqlite::types::Type::Text,
                                Box::new(error),
                            )
                        })?;

                    Ok(VersionEntry {
                        id: row.get(0)?,
                        version_number: row.get(1)?,
                        description: row.get(2)?,
                        created_at,
                        change_count: row.get::<_, i64>(4)? as usize,
                    })
                },
            )
            .optional()?
            .ok_or_else(|| anyhow!("version {version_id} was not found"))
    }

    pub fn previous_version(
        &self,
        workspace_path: &str,
        version_id: i64,
    ) -> Result<Option<VersionEntry>> {
        self.conn
            .query_row(
                "SELECT id, version_number, description, created_at, file_count
                 FROM snapshots
                 WHERE workspace_path = ?1 AND id < ?2
                 ORDER BY id DESC
                 LIMIT 1",
                params![workspace_path, version_id],
                |row| {
                    let created_at_raw: String = row.get(3)?;
                    let created_at = DateTime::parse_from_rfc3339(&created_at_raw)
                        .map(|value| value.with_timezone(&Utc))
                        .map_err(|error| {
                            rusqlite::Error::FromSqlConversionFailure(
                                3,
                                rusqlite::types::Type::Text,
                                Box::new(error),
                            )
                        })?;

                    Ok(VersionEntry {
                        id: row.get(0)?,
                        version_number: row.get(1)?,
                        description: row.get(2)?,
                        created_at,
                        change_count: row.get::<_, i64>(4)? as usize,
                    })
                },
            )
            .optional()
            .map_err(Into::into)
    }

    pub fn version_details(&self, workspace_path: &str, version_id: i64) -> Result<VersionDetails> {
        let version = self.get_version(version_id)?;
        let previous = self.previous_version(workspace_path, version_id)?;
        let current_map = self.snapshot_files_map(version_id)?;
        let previous_map = match previous.as_ref() {
            Some(entry) => self.snapshot_files_map(entry.id)?,
            None => BTreeMap::new(),
        };

        let all_paths: BTreeSet<_> = current_map
            .keys()
            .chain(previous_map.keys())
            .cloned()
            .collect();

        let mut stats = VersionStats::default();
        let mut files = Vec::new();

        for path in all_paths {
            match (previous_map.get(&path), current_map.get(&path)) {
                (None, Some(current)) => {
                    stats.add_count += 1;
                    files.push(VersionChangeEntry {
                        relative_path: path,
                        status: ChangeStatus::Added,
                        hash: Some(current.hash.clone()),
                        size: current.size,
                        is_text: is_probably_text(&current.content),
                    });
                }
                (Some(previous), None) => {
                    stats.delete_count += 1;
                    files.push(VersionChangeEntry {
                        relative_path: path,
                        status: ChangeStatus::Deleted,
                        hash: Some(previous.hash.clone()),
                        size: previous.size,
                        is_text: is_probably_text(&previous.content),
                    });
                }
                (Some(previous), Some(current))
                    if previous.hash != current.hash || previous.size != current.size =>
                {
                    stats.modify_count += 1;
                    files.push(VersionChangeEntry {
                        relative_path: path,
                        status: ChangeStatus::Modified,
                        hash: Some(current.hash.clone()),
                        size: current.size,
                        is_text: is_probably_text(&current.content)
                            || is_probably_text(&previous.content),
                    });
                }
                _ => {}
            }
        }

        files.sort_by(|left, right| left.relative_path.cmp(&right.relative_path));

        Ok(VersionDetails {
            version,
            previous_version_label: previous.map(|entry| entry.version_number),
            stats,
            files,
        })
    }

    pub fn compare_versions(
        &self,
        left_version_id: i64,
        right_version_id: i64,
    ) -> Result<VersionDiffResult> {
        let left_version = self.get_version(left_version_id)?;
        let right_version = self.get_version(right_version_id)?;
        let left = self.snapshot_files_map(left_version_id)?;
        let right = self.snapshot_files_map(right_version_id)?;

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
                        status: ChangeStatus::Added,
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
                        status: ChangeStatus::Deleted,
                        left_hash: Some(left_meta.hash.clone()),
                        right_hash: None,
                        left_size: Some(left_meta.size),
                        right_size: None,
                    });
                }
                (Some(left_meta), Some(right_meta))
                    if left_meta.hash != right_meta.hash || left_meta.size != right_meta.size =>
                {
                    modified += 1;
                    entries.push(VersionDiffEntry {
                        relative_path: path,
                        status: ChangeStatus::Modified,
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

    pub fn version_file_preview(
        &self,
        workspace_path: &str,
        version_id: i64,
        relative_path: &str,
    ) -> Result<VersionFilePreview> {
        let version = self.get_version(version_id)?;
        let previous = self.previous_version(workspace_path, version_id)?;
        let current_map = self.snapshot_files_map(version_id)?;
        let previous_map = match previous.as_ref() {
            Some(entry) => self.snapshot_files_map(entry.id)?,
            None => BTreeMap::new(),
        };

        let current = current_map.get(relative_path);
        let previous_file = previous_map.get(relative_path);
        let (status, source_left, source_right) = match (previous_file, current) {
            (None, Some(right)) => (ChangeStatus::Added, None, Some(right)),
            (Some(left), None) => (ChangeStatus::Deleted, Some(left), None),
            (Some(left), Some(right)) => (ChangeStatus::Modified, Some(left), Some(right)),
            (None, None) => {
                return Err(anyhow!(
                    "file {relative_path} was not found in version {version_id}"
                ));
            }
        };

        let is_text = source_left
            .map(|file| is_probably_text(&file.content))
            .or_else(|| source_right.map(|file| is_probably_text(&file.content)))
            .unwrap_or(false);

        if is_text {
            let (left_text, left_note) =
                decode_preview(source_left.map(|file| file.content.as_slice()));
            let (right_text, right_note) =
                decode_preview(source_right.map(|file| file.content.as_slice()));

            return Ok(VersionFilePreview {
                relative_path: relative_path.to_string(),
                status: status.clone(),
                left_label: previous
                    .as_ref()
                    .map(|entry| entry.version_number.clone())
                    .unwrap_or_else(|| "Before".to_string()),
                right_label: version.version_number,
                left_text,
                right_text,
                is_text: true,
                note: left_note.or(right_note).or_else(|| match status {
                    ChangeStatus::Added => {
                        Some("This file was added in the selected version.".to_string())
                    }
                    ChangeStatus::Deleted => {
                        Some("This file was deleted in the selected version.".to_string())
                    }
                    ChangeStatus::Modified => None,
                }),
            });
        }

        Ok(VersionFilePreview {
            relative_path: relative_path.to_string(),
            status,
            left_label: previous
                .as_ref()
                .map(|entry| entry.version_number.clone())
                .unwrap_or_else(|| "Before".to_string()),
            right_label: version.version_number,
            left_text: None,
            right_text: None,
            is_text: false,
            note: Some("This file is binary or cannot be previewed directly.".to_string()),
        })
    }

    pub fn restore_snapshot_files(&self, version_id: i64) -> Result<Vec<SnapshotFileInput>> {
        let mut statement = self.conn.prepare(
            "SELECT relative_path, hash, size_bytes, COALESCE(content, X'')
             FROM snapshot_files
             WHERE snapshot_id = ?1
             ORDER BY relative_path ASC",
        )?;

        let rows = statement.query_map(params![version_id], |row| {
            Ok(SnapshotFileInput {
                relative_path: row.get(0)?,
                hash: row.get(1)?,
                size: row.get::<_, i64>(2)? as u64,
                content: row.get(3)?,
            })
        })?;

        let mut files = Vec::new();
        for row in rows {
            files.push(row?);
        }
        Ok(files)
    }

    pub fn version_file_bytes(&self, version_id: i64, relative_path: &str) -> Result<Vec<u8>> {
        self.conn
            .query_row(
                "SELECT COALESCE(content, X'')
                 FROM snapshot_files
                 WHERE snapshot_id = ?1 AND relative_path = ?2",
                params![version_id, relative_path],
                |row| row.get(0),
            )
            .optional()?
            .ok_or_else(|| anyhow!("file {relative_path} was not found in version {version_id}"))
    }

    fn latest_snapshot_id(&self, workspace_path: &str) -> Result<Option<i64>> {
        self.conn
            .query_row(
                "SELECT id FROM snapshots
                 WHERE workspace_path = ?1
                 ORDER BY id DESC
                 LIMIT 1",
                params![workspace_path],
                |row| row.get(0),
            )
            .optional()
            .map_err(Into::into)
    }

    fn latest_fingerprint(&self, workspace_path: &str) -> Result<Option<String>> {
        self.conn
            .query_row(
                "SELECT fingerprint FROM snapshots
                 WHERE workspace_path = ?1
                 ORDER BY id DESC
                 LIMIT 1",
                params![workspace_path],
                |row| row.get(0),
            )
            .optional()
            .map_err(Into::into)
    }

    fn snapshot_files(&self, snapshot_id: i64) -> Result<Vec<SnapshotFileEntry>> {
        let mut statement = self.conn.prepare(
            "SELECT relative_path, hash, size_bytes
             FROM snapshot_files
             WHERE snapshot_id = ?1
             ORDER BY relative_path ASC",
        )?;

        let rows = statement.query_map(params![snapshot_id], |row| {
            Ok(SnapshotFileEntry {
                relative_path: row.get(0)?,
                hash: row.get(1)?,
                size: row.get::<_, i64>(2)? as u64,
            })
        })?;

        let mut files = Vec::new();
        for row in rows {
            files.push(row?);
        }
        Ok(files)
    }

    fn snapshot_files_map(&self, snapshot_id: i64) -> Result<BTreeMap<String, SnapshotFileInput>> {
        let files = self.restore_snapshot_files(snapshot_id)?;
        Ok(files
            .into_iter()
            .map(|file| (file.relative_path.clone(), file))
            .collect())
    }

    fn init_schema(&self) -> Result<()> {
        self.conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_path TEXT NOT NULL,
                snapshot_index INTEGER NOT NULL,
                version_number TEXT NOT NULL,
                description TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                created_at TEXT NOT NULL,
                file_count INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS snapshot_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_id INTEGER NOT NULL,
                relative_path TEXT NOT NULL,
                hash TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                content BLOB,
                FOREIGN KEY(snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_snapshots_workspace_id
                ON snapshots(workspace_path, id DESC);

            CREATE INDEX IF NOT EXISTS idx_snapshot_files_snapshot_id
                ON snapshot_files(snapshot_id);",
        )?;

        self.ensure_snapshot_columns()?;
        self.ensure_snapshot_file_content_column()?;
        Ok(())
    }

    fn ensure_snapshot_columns(&self) -> Result<()> {
        let columns = self.table_columns("snapshots")?;

        if !columns.iter().any(|column| column == "version_number") {
            self.conn
                .execute("ALTER TABLE snapshots ADD COLUMN version_number TEXT", [])?;
            self.conn.execute(
                "UPDATE snapshots
                 SET version_number = printf('v%04d', COALESCE(snapshot_index, id))
                 WHERE version_number IS NULL OR version_number = ''",
                [],
            )?;
        }

        if !columns.iter().any(|column| column == "description") {
            self.conn
                .execute("ALTER TABLE snapshots ADD COLUMN description TEXT", [])?;
            self.conn.execute(
                "UPDATE snapshots
                 SET description = COALESCE(summary, label, 'Imported snapshot')
                 WHERE description IS NULL OR description = ''",
                [],
            )?;
        }

        if !columns.iter().any(|column| column == "file_count") {
            self.conn
                .execute("ALTER TABLE snapshots ADD COLUMN file_count INTEGER", [])?;
            self.conn.execute(
                "UPDATE snapshots
                 SET file_count = (
                     SELECT COUNT(*)
                     FROM snapshot_files
                     WHERE snapshot_files.snapshot_id = snapshots.id
                 )
                 WHERE file_count IS NULL",
                [],
            )?;
        }

        Ok(())
    }

    fn table_columns(&self, table_name: &str) -> Result<Vec<String>> {
        let sql = format!("PRAGMA table_info({table_name})");
        let mut statement = self.conn.prepare(&sql)?;
        let rows = statement.query_map([], |row| row.get::<_, String>(1))?;
        let mut columns = Vec::new();
        for row in rows {
            columns.push(row?);
        }
        Ok(columns)
    }

    fn ensure_snapshot_file_content_column(&self) -> Result<()> {
        let has_content = self
            .table_columns("snapshot_files")?
            .iter()
            .any(|column| column == "content");

        if !has_content {
            self.conn
                .execute("ALTER TABLE snapshot_files ADD COLUMN content BLOB", [])?;
        }

        Ok(())
    }
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

fn decode_preview(bytes: Option<&[u8]>) -> (Option<String>, Option<String>) {
    const PREVIEW_LIMIT: usize = 200 * 1024;

    let Some(bytes) = bytes else {
        return (None, None);
    };

    let truncated = bytes.len() > PREVIEW_LIMIT;
    let sample = &bytes[..bytes.len().min(PREVIEW_LIMIT)];
    let text = String::from_utf8_lossy(sample).replace('\r', "");
    let note = truncated.then(|| "Preview is truncated to the first 200 KB.".to_string());
    (Some(text), note)
}

#[cfg(test)]
mod tests {
    use super::{Repository, SnapshotFileInput, SnapshotInput};

    #[test]
    fn saves_versions_and_skips_duplicate_fingerprint() {
        let mut repo = Repository::open_in_memory().expect("repo should open");
        let workspace_path = "H:/workspace/demo".to_string();
        let files = vec![SnapshotFileInput {
            relative_path: "src/main.rs".to_string(),
            hash: "abc123".to_string(),
            size: 128,
            content: b"fn main() {}".to_vec(),
        }];

        let first = repo
            .create_version(SnapshotInput {
                workspace_path: workspace_path.clone(),
                fingerprint: "fp-1".to_string(),
                description: "Initial snapshot".to_string(),
                files: files.clone(),
            })
            .expect("first version should save");
        assert!(first.is_some());

        let duplicate = repo
            .create_version(SnapshotInput {
                workspace_path: workspace_path.clone(),
                fingerprint: "fp-1".to_string(),
                description: "Duplicate".to_string(),
                files: files.clone(),
            })
            .expect("duplicate should succeed");
        assert!(duplicate.is_none());

        let second = repo
            .create_version(SnapshotInput {
                workspace_path: workspace_path.clone(),
                fingerprint: "fp-2".to_string(),
                description: "Second snapshot".to_string(),
                files,
            })
            .expect("second version should save");
        assert!(second.is_some());

        let versions = repo
            .list_versions(&workspace_path, 10)
            .expect("versions should load");
        assert_eq!(versions.len(), 2);
        assert_eq!(versions[0].version_number, "v0002");
        assert_eq!(versions[1].version_number, "v0001");
    }
}
