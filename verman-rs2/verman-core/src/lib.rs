use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum ChangeStatus {
    Added,
    Modified,
    Deleted,
}

impl ChangeStatus {
    pub fn code(&self) -> &'static str {
        match self {
            Self::Added => "add",
            Self::Modified => "modify",
            Self::Deleted => "delete",
        }
    }

    pub fn short_label(&self) -> &'static str {
        match self {
            Self::Added => "Added",
            Self::Modified => "Modified",
            Self::Deleted => "Deleted",
        }
    }

    pub fn from_code(code: &str) -> Self {
        match code {
            "add" => Self::Added,
            "delete" => Self::Deleted,
            _ => Self::Modified,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ChangeEntry {
    pub relative_path: String,
    pub status: ChangeStatus,
    pub size: u64,
    pub hash: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct SnapshotFileEntry {
    pub relative_path: String,
    pub hash: String,
    pub size: u64,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct VersionEntry {
    pub id: i64,
    pub version_number: String,
    pub created_at: DateTime<Utc>,
    pub description: String,
    pub change_count: usize,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct VersionDiffEntry {
    pub relative_path: String,
    pub status: ChangeStatus,
    pub left_hash: Option<String>,
    pub right_hash: Option<String>,
    pub left_size: Option<u64>,
    pub right_size: Option<u64>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct VersionDiffResult {
    pub left_version_id: i64,
    pub right_version_id: i64,
    pub left_version_label: String,
    pub right_version_label: String,
    pub added: usize,
    pub modified: usize,
    pub deleted: usize,
    pub entries: Vec<VersionDiffEntry>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct VersionChangeEntry {
    pub relative_path: String,
    pub status: ChangeStatus,
    pub hash: Option<String>,
    pub size: u64,
    pub is_text: bool,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize, PartialEq, Eq)]
pub struct VersionStats {
    pub add_count: usize,
    pub modify_count: usize,
    pub delete_count: usize,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct VersionDetails {
    pub version: VersionEntry,
    pub previous_version_label: Option<String>,
    pub stats: VersionStats,
    pub files: Vec<VersionChangeEntry>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct VersionFilePreview {
    pub relative_path: String,
    pub status: ChangeStatus,
    pub left_label: String,
    pub right_label: String,
    pub left_text: Option<String>,
    pub right_text: Option<String>,
    pub is_text: bool,
    pub note: Option<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct WorkspaceData {
    pub workspace_path: String,
    pub total_files: usize,
    pub total_versions: usize,
    pub changed_files: usize,
    pub changes: Vec<ChangeEntry>,
    pub versions: Vec<VersionEntry>,
    pub ignore_rules: String,
}

impl WorkspaceData {
    pub fn empty(workspace_path: impl Into<String>) -> Self {
        Self {
            workspace_path: workspace_path.into(),
            total_files: 0,
            total_versions: 0,
            changed_files: 0,
            changes: Vec::new(),
            versions: Vec::new(),
            ignore_rules: String::new(),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ContextMenuStatus {
    pub supported: bool,
    pub installed: bool,
    pub command_path: Option<String>,
    pub detail: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct AppSettings {
    pub language: String,
    pub backup_before_restore: bool,
}

impl Default for AppSettings {
    fn default() -> Self {
        Self {
            language: "zh".to_string(),
            backup_before_restore: true,
        }
    }
}
