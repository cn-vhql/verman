use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
pub struct WorkspaceData {
    pub workspace_path: String,
    pub total_files: usize,
    pub total_versions: usize,
    pub changed_files: usize,
    pub changes: Vec<ChangeEntry>,
    pub versions: Vec<VersionEntry>,
    pub ignore_rules: String,
}

#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
pub struct ChangeEntry {
    pub relative_path: String,
    pub status: String,
    pub hash: String,
    pub size: u64,
}

#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
pub struct VersionEntry {
    pub id: i64,
    pub version_number: String,
    pub created_at: String,
    pub description: String,
    pub change_count: usize,
}

#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
pub struct VersionDiffEntry {
    pub relative_path: String,
    pub status: String,
    pub left_hash: Option<String>,
    pub right_hash: Option<String>,
    pub left_size: Option<u64>,
    pub right_size: Option<u64>,
}

#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
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

#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
pub struct VersionChangeEntry {
    pub relative_path: String,
    pub status: String,
    pub hash: Option<String>,
    pub size: u64,
    pub is_text: bool,
}

#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
pub struct VersionStats {
    pub add_count: usize,
    pub modify_count: usize,
    pub delete_count: usize,
}

#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
pub struct VersionDetails {
    pub version: VersionEntry,
    pub previous_version_label: Option<String>,
    pub stats: VersionStats,
    pub files: Vec<VersionChangeEntry>,
}

#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
pub struct VersionFilePreview {
    pub relative_path: String,
    pub status: String,
    pub left_label: String,
    pub right_label: String,
    pub left_text: Option<String>,
    pub right_text: Option<String>,
    pub is_text: bool,
    pub can_open_external: bool,
    pub note: Option<String>,
}

#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
pub struct OpenExternalResult {
    pub temp_path: String,
}

#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
pub struct ExportResult {
    pub target_path: String,
    pub file_count: usize,
}

#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
pub struct ContextMenuStatus {
    pub supported: bool,
    pub installed: bool,
    pub command_path: Option<String>,
    pub detail: String,
}

#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
pub struct LaunchContext {
    pub startup_path: Option<String>,
}

#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
pub struct StatusNotice {
    pub title: String,
    pub body: String,
}
