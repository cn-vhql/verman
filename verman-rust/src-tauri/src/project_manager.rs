use std::path::{Path, PathBuf};

use crate::database::DatabaseManager;
use crate::file_manager::FileManager;
use crate::file_watcher::FileWatcher;
use crate::project_paths;
use crate::version_manager::VersionManager;

pub struct ProjectManager {
    pub current_project_path: Option<PathBuf>,
    pub version_manager: Option<VersionManager>,
    pub file_watcher: Option<FileWatcher>,
}

impl ProjectManager {
    pub fn new() -> Self {
        Self {
            current_project_path: None,
            version_manager: None,
            file_watcher: None,
        }
    }

    pub fn create_project(
        &mut self,
        workspace_path: &Path,
        config_ignore_patterns: Vec<String>,
    ) -> Result<bool, String> {
        let workspace_path = workspace_path.to_owned();
        if !workspace_path.is_dir() {
            return Ok(false);
        }
        if project_paths::is_project_workspace(&workspace_path) {
            return Ok(false);
        }

        project_paths::ensure_metadata_dir(&workspace_path)
            .map_err(|e| format!("Failed to create metadata dir: {}", e))?;
        self.create_ignore_file(&workspace_path);

        let db_path = project_paths::get_project_database_path(&workspace_path);
        let db_manager =
            DatabaseManager::new(&db_path).map_err(|e| format!("Failed to init DB: {}", e))?;
        db_manager
            .set_config("project_path", &workspace_path.to_string_lossy())
            .map_err(|e| format!("Failed to set config: {}", e))?;
        db_manager
            .set_config(
                "create_time",
                &chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string(),
            )
            .map_err(|e| format!("Failed to set config: {}", e))?;

        let file_manager = FileManager::new(&workspace_path);
        let vm = VersionManager::new(db_manager, file_manager, config_ignore_patterns);

        self.current_project_path = Some(workspace_path);
        self.version_manager = Some(vm);
        Ok(true)
    }

    pub fn open_project(
        &mut self,
        workspace_path: &Path,
        config_ignore_patterns: Vec<String>,
    ) -> Result<bool, String> {
        let workspace_path = workspace_path.to_owned();
        if !workspace_path.is_dir() {
            return Ok(false);
        }

        self.migrate_legacy_layout(&workspace_path);

        let db_path = match project_paths::find_existing_database_path(&workspace_path) {
            Some(p) => p,
            None => return Ok(false),
        };

        let db_manager =
            DatabaseManager::new(&db_path).map_err(|e| format!("Failed to open DB: {}", e))?;

        let file_manager = FileManager::new(&workspace_path);
        let vm = VersionManager::new(db_manager, file_manager, config_ignore_patterns);

        self.current_project_path = Some(workspace_path);
        self.version_manager = Some(vm);
        Ok(true)
    }

    pub fn close(&mut self) {
        if let Some(ref vm) = self.version_manager {
            if let Ok(fm) = vm.file_manager.lock() {
                fm.save_hash_cache();
            }
        }
        self.file_watcher = None;
        self.version_manager = None;
        self.current_project_path = None;
    }

    pub fn start_watcher(&mut self, path: &Path, app_handle: tauri::AppHandle) {
        self.file_watcher = FileWatcher::start(path.to_path_buf(), app_handle).ok();
    }

    pub fn is_open(&self) -> bool {
        self.current_project_path.is_some() && self.version_manager.is_some()
    }

    pub fn get_project_path(&self) -> Option<&Path> {
        self.current_project_path.as_deref()
    }

    fn migrate_legacy_layout(&self, workspace_path: &Path) {
        let legacy_db = project_paths::get_legacy_database_path(workspace_path);
        let new_db = project_paths::get_project_database_path(workspace_path);
        if !legacy_db.exists() || new_db.exists() {
            return;
        }

        if let Err(e) = project_paths::ensure_metadata_dir(workspace_path) {
            tracing::warn!(error = %e, "Cannot create metadata dir for migration");
            return;
        }

        // Migrate database sidecar files
        for (legacy, new) in project_paths::iter_database_sidecar_paths(&legacy_db)
            .into_iter()
            .zip(project_paths::iter_database_sidecar_paths(&new_db))
        {
            if legacy.exists() {
                if let Err(e) = std::fs::rename(&legacy, &new) {
                    tracing::warn!(error = %e, "Failed to migrate {:?}", legacy);
                } else {
                    tracing::info!("Migrated {:?} -> {:?}", legacy, new);
                }
            }
        }

        // Migrate backup files
        let pattern = format!("{}.bak.*", legacy_db.display());
        if let Ok(entries) = glob::glob(&pattern) {
            for entry in entries.flatten() {
                let suffix = entry
                    .to_string_lossy()
                    .split(&format!("{}.bak.", legacy_db.display()))
                    .nth(1)
                    .unwrap_or("")
                    .to_string();
                let new_backup = format!("{}.bak.{}", new_db.display(), suffix);
                if let Err(e) = std::fs::rename(&entry, Path::new(&new_backup)) {
                    tracing::warn!(error = %e, "Failed to migrate backup {:?}", entry);
                }
            }
        }

        // Migrate legacy backup directory
        let legacy_backup_dir = project_paths::get_legacy_backup_dir(workspace_path);
        let backup_dir = project_paths::get_backup_dir(workspace_path);
        if legacy_backup_dir.is_dir() {
            if backup_dir.exists() {
                Self::merge_directories(&legacy_backup_dir, &backup_dir);
                std::fs::remove_dir_all(&legacy_backup_dir).ok();
            } else {
                std::fs::rename(&legacy_backup_dir, &backup_dir).ok();
            }
            tracing::info!("Migrated backup dir {:?} -> {:?}", legacy_backup_dir, backup_dir);
        }
    }

    fn merge_directories(source: &Path, target: &Path) {
        let walker = walkdir::WalkDir::new(source);
        for entry in walker.into_iter().flatten() {
            if entry.file_type().is_file() {
                let relative = entry.path().strip_prefix(source).unwrap_or(entry.path());
                let dest = target.join(relative);
                if let Some(parent) = dest.parent() {
                    std::fs::create_dir_all(parent).ok();
                }
                std::fs::rename(entry.path(), &dest).ok();
            }
        }
    }

    fn create_ignore_file(&self, workspace_path: &Path) {
        let ignore_path = project_paths::get_ignore_file_path(workspace_path);
        if ignore_path.exists() {
            return;
        }

        let content = r#"# VerMan 忽略文件
# 该文件用于指定版本管理中需要忽略的文件和目录

# VerMan 元数据
.verman/
.verman.db
.verman.db-shm
.verman.db-wal
.verman.db-journal
.verman.db.bak.*
.verman_backup/

# Python 相关
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
dist/
*.egg-info/
*.egg

# 虚拟环境
.env
.venv/
env/
venv/
ENV/

# IDE 相关
.vscode/
.idea/
*.swp
*.swo
*~

# 系统文件
.DS_Store
Thumbs.db
desktop.ini

# 临时文件
*.tmp
*.temp
*.log
*.bak
*.backup
"#;

        std::fs::write(&ignore_path, content).ok();
    }
}
