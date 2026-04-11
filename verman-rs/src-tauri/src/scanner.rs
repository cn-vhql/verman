use crate::models::{ChangeEntry, FileRecord, SnapshotMeta, VersionBlob};
use anyhow::{anyhow, Context, Result};
use ignore::gitignore::{Gitignore, GitignoreBuilder};
use std::collections::{BTreeMap, BTreeSet};
use std::fs::{self, File};
use std::io::{BufReader, Read};
use std::path::{Path, PathBuf};
use walkdir::WalkDir;

const DEFAULT_IGNORE_PATTERNS: &[&str] = &[
    ".verman.db",
    ".verman_backup/",
    ".verman_temp/",
    "__pycache__/",
    ".git/",
    ".svn/",
    ".hg/",
    "*.pyc",
    "*.pyo",
    "*.tmp",
    "*.temp",
    "*.log",
    "Thumbs.db",
    ".DS_Store",
    "node_modules/",
    "target/",
    "dist/",
];

const DEFAULT_IGNORE_RULES: &str =
    "# VerMan ignore rules\n# One glob per line. Lines starting with # are comments.\n\n";

pub fn scan_workspace(workspace: &Path) -> Result<BTreeMap<String, FileRecord>> {
    if !workspace.exists() {
        return Err(anyhow!("Workspace does not exist: {}", workspace.display()));
    }

    let ignore_matcher = build_ignore_matcher(workspace)?;
    let mut files = BTreeMap::new();

    for entry in WalkDir::new(workspace)
        .follow_links(false)
        .into_iter()
        .filter_entry(|entry| {
            filter_entry(
                entry.path(),
                entry.file_type().is_dir(),
                &ignore_matcher,
                workspace,
            )
        })
    {
        let entry = entry?;
        if !entry.file_type().is_file() {
            continue;
        }

        let path = entry.path();
        if ignore_matcher
            .matched_path_or_any_parents(path, false)
            .is_ignore()
        {
            continue;
        }

        let metadata = entry.metadata()?;
        let size = metadata.len();
        if size > 100 * 1024 * 1024 {
            continue;
        }

        let relative_path = path
            .strip_prefix(workspace)
            .context("Failed to compute relative path")?
            .to_string_lossy()
            .replace('\\', "/");

        let hash = hash_file(path)?;
        files.insert(
            relative_path.clone(),
            FileRecord {
                relative_path,
                hash,
                size,
                absolute_path: path.to_path_buf(),
            },
        );
    }

    Ok(files)
}

pub fn detect_changes(
    current: &BTreeMap<String, FileRecord>,
    previous: &BTreeMap<String, SnapshotMeta>,
) -> Vec<ChangeEntry> {
    let mut changes = Vec::new();
    let current_paths: BTreeSet<_> = current.keys().cloned().collect();
    let previous_paths: BTreeSet<_> = previous.keys().cloned().collect();

    for path in current_paths.difference(&previous_paths) {
        if let Some(file) = current.get(path) {
            changes.push(ChangeEntry {
                relative_path: path.clone(),
                status: "add".to_string(),
                hash: file.hash.clone(),
                size: file.size,
            });
        }
    }

    for path in current_paths.intersection(&previous_paths) {
        if let (Some(current_file), Some(previous_file)) = (current.get(path), previous.get(path)) {
            if current_file.hash != previous_file.hash {
                changes.push(ChangeEntry {
                    relative_path: path.clone(),
                    status: "modify".to_string(),
                    hash: current_file.hash.clone(),
                    size: current_file.size,
                });
            }
        }
    }

    for path in previous_paths.difference(&current_paths) {
        if let Some(file) = previous.get(path) {
            changes.push(ChangeEntry {
                relative_path: path.clone(),
                status: "delete".to_string(),
                hash: file.hash.clone(),
                size: file.size,
            });
        }
    }

    changes
}

pub fn changed_blobs(
    current: &BTreeMap<String, FileRecord>,
    changes: &[ChangeEntry],
) -> Result<Vec<VersionBlob>> {
    let mut blobs = Vec::new();

    for change in changes {
        if change.status == "delete" {
            continue;
        }

        let file = current
            .get(&change.relative_path)
            .with_context(|| format!("Missing changed file {}", change.relative_path))?;

        blobs.push(VersionBlob {
            relative_path: change.relative_path.clone(),
            hash: change.hash.clone(),
            content: fs::read(&file.absolute_path)
                .with_context(|| format!("Failed to read file {}", file.absolute_path.display()))?,
        });
    }

    Ok(blobs)
}

pub fn backup_current_state(
    workspace: &Path,
    current: &BTreeMap<String, FileRecord>,
) -> Result<()> {
    if current.is_empty() {
        return Ok(());
    }

    let stamp = chrono::Local::now().format("%Y%m%d_%H%M%S").to_string();
    let backup_root = workspace
        .join(".verman_backup")
        .join(format!("backup_{stamp}"));
    fs::create_dir_all(&backup_root)?;

    for file in current.values() {
        let target = backup_root.join(&file.relative_path);
        if let Some(parent) = target.parent() {
            fs::create_dir_all(parent)?;
        }
        fs::copy(&file.absolute_path, &target).with_context(|| {
            format!(
                "Failed to backup file {} -> {}",
                file.absolute_path.display(),
                target.display()
            )
        })?;
    }

    Ok(())
}

pub fn export_payload(target_root: &Path, payload: &[VersionBlob]) -> Result<usize> {
    fs::create_dir_all(target_root)?;

    for file in payload {
        let target = target_root.join(&file.relative_path);
        if let Some(parent) = target.parent() {
            fs::create_dir_all(parent)?;
        }
        fs::write(&target, &file.content)
            .with_context(|| format!("Failed to export file {}", target.display()))?;
    }

    Ok(payload.len())
}

pub fn cleanup_empty_directories(workspace: &Path) -> Result<()> {
    let mut directories: Vec<PathBuf> = WalkDir::new(workspace)
        .min_depth(1)
        .into_iter()
        .filter_map(|entry| entry.ok())
        .filter(|entry| entry.file_type().is_dir())
        .map(|entry| entry.path().to_path_buf())
        .collect();

    directories.sort_by_key(|path| std::cmp::Reverse(path.components().count()));

    for dir in directories {
        if dir.ends_with(".verman_backup") {
            continue;
        }

        if fs::read_dir(&dir)?.next().is_none() {
            let _ = fs::remove_dir(&dir);
        }
    }

    Ok(())
}

pub fn load_ignore_rules_text(workspace: &Path) -> Result<String> {
    let ignore_file = workspace.join(".vermanignore");
    if ignore_file.exists() {
        return fs::read_to_string(ignore_file).context("Failed to read .vermanignore");
    }

    Ok(DEFAULT_IGNORE_RULES.to_string())
}

pub fn save_ignore_rules_text(workspace: &Path, contents: &str) -> Result<()> {
    fs::write(workspace.join(".vermanignore"), contents).context("Failed to write .vermanignore")
}

fn filter_entry(path: &Path, is_dir: bool, matcher: &Gitignore, workspace: &Path) -> bool {
    if path == workspace {
        return true;
    }

    !matcher
        .matched_path_or_any_parents(path, is_dir)
        .is_ignore()
}

fn build_ignore_matcher(workspace: &Path) -> Result<Gitignore> {
    let mut builder = GitignoreBuilder::new(workspace);

    for pattern in DEFAULT_IGNORE_PATTERNS {
        builder
            .add_line(None, pattern)
            .with_context(|| format!("Invalid ignore rule: {pattern}"))?;
    }

    let ignore_file = workspace.join(".vermanignore");
    if ignore_file.exists() {
        builder.add(ignore_file);
    }

    builder.build().map_err(Into::into)
}

fn hash_file(path: &Path) -> Result<String> {
    let file = File::open(path)?;
    let mut reader = BufReader::new(file);
    let mut hasher = blake3::Hasher::new();
    let mut buffer = [0u8; 64 * 1024];

    loop {
        let read = reader.read(&mut buffer)?;
        if read == 0 {
            break;
        }
        hasher.update(&buffer[..read]);
    }

    Ok(hasher.finalize().to_hex().to_string())
}
