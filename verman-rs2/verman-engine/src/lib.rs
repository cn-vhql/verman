use anyhow::{Context, Result, anyhow};
use blake3::Hasher;
use ignore::WalkBuilder;
use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use verman_core::{
    AppSettings, ChangeEntry, ChangeStatus, SnapshotFileEntry, VersionDetails, VersionDiffResult,
    VersionFilePreview, WorkspaceData,
};
use verman_storage::{Repository, SnapshotFileInput, SnapshotInput};

#[derive(Clone, Debug)]
struct WorkspaceFile {
    relative_path: String,
    hash: String,
    size: u64,
    content: Vec<u8>,
}

pub struct Engine {
    repo: Repository,
    workspace_root: PathBuf,
}

impl Engine {
    pub fn bootstrap() -> Result<Self> {
        let workspace_root =
            std::env::current_dir().context("failed to resolve current directory")?;
        let repo_path = workspace_root.join(".verman").join("verman.db");
        Ok(Self {
            repo: Repository::open_or_create(&repo_path)?,
            workspace_root,
        })
    }

    pub fn open_workspace(&mut self, path: impl Into<PathBuf>) -> Result<WorkspaceData> {
        let workspace_root = path.into();
        validate_workspace(&workspace_root)?;
        let repo_path = workspace_root.join(".verman").join("verman.db");
        self.repo = Repository::open_or_create(&repo_path)?;
        self.workspace_root = workspace_root;
        self.dashboard()
    }

    pub fn workspace_root(&self) -> &Path {
        &self.workspace_root
    }

    pub fn settings(&self) -> Result<AppSettings> {
        self.repo.load_settings()
    }

    pub fn save_settings(&self, settings: &AppSettings) -> Result<()> {
        self.repo.save_settings(settings)
    }

    pub fn dashboard(&mut self) -> Result<WorkspaceData> {
        let workspace_root = self.workspace_root.clone();
        self.scan_workspace(&workspace_root)
    }

    pub fn create_version(&mut self, description: &str) -> Result<WorkspaceData> {
        let workspace_root = self.workspace_root.clone();
        let current_files = collect_workspace_files(&workspace_root)?;
        let workspace_path = workspace_root.display().to_string();
        let previous_snapshot = self.repo.latest_snapshot_files(&workspace_path)?;
        let changes = detect_changes(&current_files, &previous_snapshot);

        if !previous_snapshot.is_empty() && changes.is_empty() {
            return Err(anyhow!("no file changes were detected"));
        }

        let description = if description.trim().is_empty() {
            format!(
                "Snapshot from {}",
                chrono::Local::now().format("%Y-%m-%d %H:%M:%S")
            )
        } else {
            description.trim().to_string()
        };

        self.repo.create_version(SnapshotInput {
            workspace_path,
            fingerprint: workspace_fingerprint(&workspace_root, &current_files),
            description,
            files: current_files
                .into_iter()
                .map(|file| SnapshotFileInput {
                    relative_path: file.relative_path,
                    hash: file.hash,
                    size: file.size,
                    content: file.content,
                })
                .collect(),
        })?;

        self.dashboard()
    }

    pub fn rollback_to_version(
        &mut self,
        version_id: i64,
        backup_current: bool,
    ) -> Result<WorkspaceData> {
        let workspace_root = self.workspace_root.clone();
        let current_files = collect_workspace_files(&workspace_root)?;
        if backup_current {
            backup_current_state(&workspace_root, &current_files)?;
        }

        let payload = self.repo.restore_snapshot_files(version_id)?;
        let expected: BTreeMap<_, _> = payload
            .iter()
            .map(|file| (file.relative_path.clone(), file))
            .collect();

        for file in &current_files {
            if !expected.contains_key(&file.relative_path) {
                let target = workspace_root.join(&file.relative_path);
                if target.exists() {
                    fs::remove_file(&target)
                        .with_context(|| format!("failed to delete {}", target.display()))?;
                }
            }
        }

        for file in payload {
            let target = workspace_root.join(&file.relative_path);
            if let Some(parent) = target.parent() {
                fs::create_dir_all(parent)?;
            }
            fs::write(&target, file.content)
                .with_context(|| format!("failed to write {}", target.display()))?;
        }

        cleanup_empty_directories(&workspace_root)?;
        self.dashboard()
    }

    pub fn version_details(&self, version_id: i64) -> Result<VersionDetails> {
        self.repo
            .version_details(&self.workspace_root.display().to_string(), version_id)
    }

    pub fn version_file_preview(
        &self,
        version_id: i64,
        relative_path: &str,
    ) -> Result<VersionFilePreview> {
        self.repo.version_file_preview(
            &self.workspace_root.display().to_string(),
            version_id,
            relative_path,
        )
    }

    pub fn compare_versions(
        &self,
        left_version_id: i64,
        right_version_id: i64,
    ) -> Result<VersionDiffResult> {
        self.repo
            .compare_versions(left_version_id, right_version_id)
    }

    pub fn open_version_file_external(&self, version_id: i64, relative_path: &str) -> Result<()> {
        let bytes = self.repo.version_file_bytes(version_id, relative_path)?;
        let staging_root = std::env::temp_dir()
            .join("verman-rs2-preview")
            .join(version_id.to_string());
        let target = staging_root.join(relative_path);
        if let Some(parent) = target.parent() {
            fs::create_dir_all(parent)?;
        }
        fs::write(&target, bytes)
            .with_context(|| format!("failed to write preview file {}", target.display()))?;

        #[cfg(target_os = "windows")]
        {
            Command::new("cmd")
                .args(["/C", "start", "", &target.to_string_lossy()])
                .spawn()
                .with_context(|| format!("failed to open {}", target.display()))?;
        }

        #[cfg(not(target_os = "windows"))]
        {
            let _ = target;
            return Err(anyhow!("external open is only implemented on windows"));
        }

        Ok(())
    }

    pub fn health_fingerprint(&self, dashboard: &WorkspaceData) -> String {
        let mut hasher = Hasher::new();
        hasher.update(dashboard.workspace_path.as_bytes());
        hasher.update(dashboard.total_files.to_string().as_bytes());
        hasher.update(dashboard.changed_files.to_string().as_bytes());
        hasher.update(dashboard.total_versions.to_string().as_bytes());
        hasher.finalize().to_hex()[..12].to_string()
    }

    fn scan_workspace(&mut self, workspace_root: &Path) -> Result<WorkspaceData> {
        let mut dashboard = WorkspaceData::empty(workspace_root.display().to_string());
        let current_files = collect_workspace_files(workspace_root)?;
        let workspace_path = dashboard.workspace_path.clone();
        let previous_snapshot = self.repo.latest_snapshot_files(&workspace_path)?;
        let changes = detect_changes(&current_files, &previous_snapshot);
        let versions = self.repo.list_versions(&workspace_path, 50)?;

        dashboard.total_files = current_files.len();
        dashboard.total_versions = versions.len();
        dashboard.changed_files = changes.len();
        dashboard.changes = changes;
        dashboard.versions = versions;
        dashboard.ignore_rules = load_ignore_rules_text(workspace_root)?;
        Ok(dashboard)
    }
}

fn validate_workspace(workspace_root: &Path) -> Result<()> {
    if !workspace_root.exists() {
        return Err(anyhow!(
            "workspace does not exist: {}",
            workspace_root.display()
        ));
    }
    if !workspace_root.is_dir() {
        return Err(anyhow!(
            "workspace is not a directory: {}",
            workspace_root.display()
        ));
    }
    Ok(())
}

fn collect_workspace_files(workspace_root: &Path) -> Result<Vec<WorkspaceFile>> {
    let mut files = Vec::new();
    let walker = WalkBuilder::new(workspace_root)
        .hidden(false)
        .git_ignore(true)
        .git_exclude(true)
        .parents(true)
        .build();

    for entry in walker {
        let entry = entry?;
        let path = entry.path();
        if path.is_dir() {
            continue;
        }

        let relative_path = match path.strip_prefix(workspace_root) {
            Ok(relative) => relative.to_string_lossy().replace('\\', "/"),
            Err(_) => path.to_string_lossy().replace('\\', "/"),
        };

        if should_skip_path(&relative_path) {
            continue;
        }

        let content =
            fs::read(path).with_context(|| format!("failed to read {}", path.display()))?;
        let size = content.len() as u64;
        let hash = blake3::hash(&content).to_hex()[..12].to_string();

        files.push(WorkspaceFile {
            relative_path,
            hash,
            size,
            content,
        });
    }

    files.sort_by(|left, right| left.relative_path.cmp(&right.relative_path));
    Ok(files)
}

fn detect_changes(
    current_files: &[WorkspaceFile],
    previous_files: &[SnapshotFileEntry],
) -> Vec<ChangeEntry> {
    let current_map = current_files
        .iter()
        .map(|file| (file.relative_path.clone(), file))
        .collect::<BTreeMap<_, _>>();
    let previous_map = previous_files
        .iter()
        .map(|file| (file.relative_path.clone(), file))
        .collect::<BTreeMap<_, _>>();
    let mut changes = Vec::new();

    for current in current_files {
        match previous_map.get(&current.relative_path) {
            None => changes.push(ChangeEntry {
                relative_path: current.relative_path.clone(),
                status: ChangeStatus::Added,
                size: current.size,
                hash: current.hash.clone(),
            }),
            Some(previous) if previous.hash != current.hash || previous.size != current.size => {
                changes.push(ChangeEntry {
                    relative_path: current.relative_path.clone(),
                    status: ChangeStatus::Modified,
                    size: current.size,
                    hash: current.hash.clone(),
                });
            }
            Some(_) => {}
        }
    }

    for previous in previous_files {
        if !current_map.contains_key(&previous.relative_path) {
            changes.push(ChangeEntry {
                relative_path: previous.relative_path.clone(),
                status: ChangeStatus::Deleted,
                size: previous.size,
                hash: previous.hash.clone(),
            });
        }
    }

    changes.sort_by(|left, right| left.relative_path.cmp(&right.relative_path));
    changes
}

fn load_ignore_rules_text(workspace_root: &Path) -> Result<String> {
    let ignore_path = workspace_root.join(".vermanignore");
    if !ignore_path.exists() {
        return Ok(String::new());
    }

    std::fs::read_to_string(&ignore_path)
        .with_context(|| format!("failed to read {}", ignore_path.display()))
}

fn workspace_fingerprint(workspace_root: &Path, files: &[WorkspaceFile]) -> String {
    let mut hasher = Hasher::new();
    hasher.update(workspace_root.to_string_lossy().as_bytes());

    for file in files {
        hasher.update(file.relative_path.as_bytes());
        hasher.update(file.size.to_string().as_bytes());
        hasher.update(file.hash.as_bytes());
    }

    hasher.finalize().to_hex()[..16].to_string()
}

fn should_skip_path(relative_path: &str) -> bool {
    relative_path == ".verman/verman.db"
        || relative_path.starts_with(".git/")
        || relative_path.starts_with(".verman/")
        || relative_path.starts_with(".verman_backup/")
        || relative_path.starts_with("target/")
        || relative_path.starts_with(".idea/")
        || relative_path.starts_with(".vscode/")
        || relative_path.starts_with("node_modules/")
        || relative_path.starts_with(".venv/")
        || relative_path.starts_with("venv/")
}

fn backup_current_state(workspace_root: &Path, current_files: &[WorkspaceFile]) -> Result<()> {
    if current_files.is_empty() {
        return Ok(());
    }

    let stamp = chrono::Local::now().format("%Y%m%d_%H%M%S").to_string();
    let backup_root = workspace_root
        .join(".verman_backup")
        .join(format!("backup_{stamp}"));
    fs::create_dir_all(&backup_root)?;

    for file in current_files {
        let target = backup_root.join(&file.relative_path);
        if let Some(parent) = target.parent() {
            fs::create_dir_all(parent)?;
        }
        fs::write(&target, &file.content)
            .with_context(|| format!("failed to backup {}", target.display()))?;
    }

    Ok(())
}

fn cleanup_empty_directories(workspace: &Path) -> Result<()> {
    let mut directories = Vec::new();
    for entry in WalkBuilder::new(workspace).hidden(false).build() {
        let entry = entry?;
        if entry.path().is_dir() && entry.path() != workspace {
            directories.push(entry.into_path());
        }
    }

    directories.sort_by_key(|path| std::cmp::Reverse(path.components().count()));

    for dir in directories {
        if dir.ends_with(".verman") || dir.ends_with(".verman_backup") {
            continue;
        }
        if fs::read_dir(&dir)?.next().is_none() {
            let _ = fs::remove_dir(&dir);
        }
    }

    Ok(())
}
