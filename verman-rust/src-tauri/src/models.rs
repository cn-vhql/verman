use serde::{Deserialize, Serialize};
use std::collections::HashMap;

pub const CURRENT_SCHEMA_VERSION: &str = "2";

pub const DEFAULT_IGNORE_PATTERNS: &[&str] = &[
    ".verman/", ".verman.db", ".verman.db-shm", ".verman.db-wal", ".verman.db-journal",
    ".verman.db.bak.*", "*.db", "*.db-shm", "*.db-wal", "*.db-journal", "*.sqlite", "*.sqlite3",
    ".verman_backup/", ".verman_temp/", "__pycache__/", "*.pyc", "*.pyo", ".git/", ".svn/", ".hg/",
    "*.tmp", "*.temp", "*.log", ".DS_Store", "Thumbs.db",
];

pub const ACTIVE_FILE_STATUSES: &[&str] = &["add", "modify", "unmodified"];
pub const BLOB_STORAGE_THRESHOLD: i64 = 1_048_576; // 1 MB - files larger than this are stored as external blobs

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileState {
    pub relative_path: String,
    pub file_hash: String,
    pub file_size: i64,
    pub mtime_ns: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BlockedFile {
    pub relative_path: String,
    pub file_size: i64,
    pub reason: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChangeEntry {
    pub relative_path: String,
    pub file_hash: String,
    pub file_status: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScanSnapshot {
    pub current_files: HashMap<String, FileState>,
    pub changes: Vec<ChangeEntry>,
    pub blocked_files: Vec<BlockedFile>,
    pub scan_id: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct CreateVersionResult {
    pub success: bool,
    pub version_number: Option<String>,
    pub change_count: i64,
    pub blocked_files: Vec<BlockedFile>,
    pub warnings: Vec<String>,
    pub error: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct RollbackResult {
    pub success: bool,
    pub restored_count: i64,
    pub removed_count: i64,
    pub warnings: Vec<String>,
    pub error: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VersionInfo {
    pub id: i64,
    pub version_number: String,
    pub create_time: String,
    pub description: Option<String>,
    pub change_count: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VersionFileInfo {
    pub relative_path: String,
    pub file_hash: String,
    pub file_status: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub file_content: Option<Vec<u8>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VersionDetails {
    pub id: i64,
    pub version_number: String,
    pub create_time: String,
    pub description: Option<String>,
    pub change_count: i64,
    pub files: Vec<VersionFileInfo>,
    pub statistics: VersionStatistics,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VersionStatistics {
    pub add_count: usize,
    pub modify_count: usize,
    pub delete_count: usize,
    pub unmodified_count: usize,
    pub total_count: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VersionDiff {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub only_in_first: Option<Vec<DiffFileEntry>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub only_in_second: Option<Vec<DiffFileEntry>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub different: Option<Vec<DiffEntry>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiffFileEntry {
    pub relative_path: String,
    pub file_hash: String,
    pub file_status: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiffEntry {
    pub relative_path: String,
    pub file_in_v1: DiffSide,
    pub file_in_v2: DiffSide,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiffSide {
    pub file_hash: String,
    pub file_status: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectInfo {
    pub project_path: String,
    pub create_time: String,
    pub version_count: i64,
    pub latest_version: String,
    pub latest_time: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LogEntry {
    pub timestamp: String,
    pub level: String,
    pub action: String,
    pub details: String,
    pub project_path: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkspaceIndexEntry {
    pub file_hash: String,
    pub file_size: i64,
    pub mtime_ns: i64,
    pub last_seen_scan_id: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProgressPayload {
    pub stage: String,
    pub current: usize,
    pub total: usize,
    pub message: String,
}
