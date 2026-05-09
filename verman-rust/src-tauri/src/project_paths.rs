use std::path::{Path, PathBuf};

pub const VERMAN_DIR_NAME: &str = ".verman";
pub const PROJECT_DB_FILENAME: &str = "project.db";
pub const IGNORE_FILENAME: &str = ".vermanignore";
pub const BACKUP_DIR_NAME: &str = "backup";
pub const LEGACY_DB_FILENAME: &str = ".verman.db";
pub const LEGACY_BACKUP_DIR_NAME: &str = ".verman_backup";
pub const DATABASE_SIDE_SUFFIXES: &[&str] = &["", "-wal", "-shm", "-journal"];

pub fn get_metadata_dir(workspace_path: &Path) -> PathBuf {
    workspace_path.join(VERMAN_DIR_NAME)
}

pub fn ensure_metadata_dir(workspace_path: &Path) -> std::io::Result<PathBuf> {
    let dir = get_metadata_dir(workspace_path);
    std::fs::create_dir_all(&dir)?;
    Ok(dir)
}

pub fn get_project_database_path(workspace_path: &Path) -> PathBuf {
    get_metadata_dir(workspace_path).join(PROJECT_DB_FILENAME)
}

pub fn get_ignore_file_path(workspace_path: &Path) -> PathBuf {
    workspace_path.join(IGNORE_FILENAME)
}

pub fn get_backup_dir(workspace_path: &Path) -> PathBuf {
    get_metadata_dir(workspace_path).join(BACKUP_DIR_NAME)
}

pub fn get_legacy_database_path(workspace_path: &Path) -> PathBuf {
    workspace_path.join(LEGACY_DB_FILENAME)
}

pub fn get_legacy_backup_dir(workspace_path: &Path) -> PathBuf {
    workspace_path.join(LEGACY_BACKUP_DIR_NAME)
}

pub fn iter_database_sidecar_paths(db_path: &Path) -> Vec<PathBuf> {
    let base = db_path.to_string_lossy().to_string();
    DATABASE_SIDE_SUFFIXES
        .iter()
        .map(|suffix| PathBuf::from(format!("{}{}", base, suffix)))
        .collect()
}

pub fn find_existing_database_path(workspace_path: &Path) -> Option<PathBuf> {
    let db_path = get_project_database_path(workspace_path);
    if db_path.exists() {
        return Some(db_path);
    }
    let legacy_db_path = get_legacy_database_path(workspace_path);
    if legacy_db_path.exists() {
        return Some(legacy_db_path);
    }
    None
}

pub fn get_hash_cache_path(workspace_path: &Path) -> PathBuf {
    get_metadata_dir(workspace_path).join("hash_cache.json")
}

pub fn get_blobs_dir(workspace_path: &Path) -> PathBuf {
    get_metadata_dir(workspace_path).join("blobs")
}

pub fn get_blob_path(workspace_path: &Path, file_hash: &str) -> PathBuf {
    get_blobs_dir(workspace_path).join(file_hash)
}

pub fn is_project_workspace(workspace_path: &Path) -> bool {
    find_existing_database_path(workspace_path).is_some()
}
