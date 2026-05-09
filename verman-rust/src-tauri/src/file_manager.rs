use std::collections::HashMap;
use std::io::Read;
use std::num::NonZeroUsize;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use lru::LruCache;
use rayon::prelude::*;
use serde::{Deserialize, Serialize};
use walkdir::WalkDir;

use md5::{Md5, Digest};

use crate::models::{
    ACTIVE_FILE_STATUSES, DEFAULT_IGNORE_PATTERNS, BlockedFile, FileState, VersionFileInfo,
    WorkspaceIndexEntry,
};

pub struct FileManager {
    workspace_path: PathBuf,
    hash_cache: LruCache<String, HashEntry>,
}

#[derive(Clone, Serialize, Deserialize)]
struct HashEntry {
    file_hash: String,
    file_size: i64,
    mtime_ns: i64,
    cached_at: u64,
}

impl FileManager {
    pub fn new(workspace_path: &Path) -> Self {
        let mut mgr = Self {
            workspace_path: workspace_path.to_owned(),
            hash_cache: LruCache::new(NonZeroUsize::new(1000).unwrap()),
        };
        mgr.load_hash_cache();
        mgr
    }

    pub fn save_hash_cache(&self) {
        let entries: Vec<(String, HashEntry)> = self.hash_cache.iter().map(|(k, v)| (k.clone(), v.clone())).collect();
        let path = crate::project_paths::get_hash_cache_path(&self.workspace_path);
        if entries.is_empty() {
            let _ = std::fs::remove_file(&path);
            return;
        }
        if let Ok(json) = serde_json::to_string(&entries) {
            let _ = std::fs::write(&path, &json);
        }
    }

    fn load_hash_cache(&mut self) {
        let path = crate::project_paths::get_hash_cache_path(&self.workspace_path);
        let json = match std::fs::read_to_string(&path) {
            Ok(s) => s,
            Err(_) => return,
        };
        let entries: Vec<(String, HashEntry)> = match serde_json::from_str(&json) {
            Ok(e) => e,
            Err(_) => return,
        };
        for (key, entry) in entries {
            self.hash_cache.put(key, entry);
        }
    }

    pub fn clear_hash_cache(&mut self) {
        self.hash_cache.clear();
    }

    pub fn scan_workspace(
        &mut self,
        ignore_patterns: &[String],
        indexed_files: &HashMap<String, WorkspaceIndexEntry>,
    ) -> (HashMap<String, FileState>, Vec<BlockedFile>) {
        let mut current_files: HashMap<String, FileState> = HashMap::new();
        let blocked_files: Vec<BlockedFile> = Vec::new();
        let mut pending_hash: Vec<(String, PathBuf)> = Vec::new();
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_secs())
            .unwrap_or(0);

        for (relative_path, file_path) in self.iter_visible_files(ignore_patterns) {
            let metadata = match std::fs::metadata(&file_path) {
                Ok(m) => m,
                Err(e) => {
                    tracing::warn!(error = %e, path = %relative_path, "Skipping file");
                    continue;
                }
            };

            let file_size = metadata.len() as i64;
            let mtime_ns = metadata
                .modified()
                .ok()
                .and_then(|t| t.duration_since(UNIX_EPOCH).ok())
                .map(|d| d.as_nanos() as i64)
                .unwrap_or(0);

            // Try workspace index cache first
            let cached_hash = indexed_files.get(&relative_path).and_then(|indexed| {
                if indexed.file_size == file_size && indexed.mtime_ns == mtime_ns
                    && !indexed.file_hash.is_empty()
                {
                    Some(indexed.file_hash.clone())
                } else {
                    None
                }
            });

            // Try in-memory LRU cache
            let cached_hash = cached_hash.or_else(|| {
                self.hash_cache.get(&relative_path).and_then(|entry| {
                    if entry.file_size == file_size && entry.mtime_ns == mtime_ns
                        && now - entry.cached_at < 300
                    {
                        Some(entry.file_hash.clone())
                    } else {
                        None
                    }
                })
            });

            if let Some(hash) = cached_hash {
                current_files.insert(
                    relative_path.clone(),
                    FileState {
                        relative_path,
                        file_hash: hash,
                        file_size,
                        mtime_ns,
                    },
                );
            } else {
                pending_hash.push((relative_path, file_path));
            }
        }

        // Parallel phase: compute hashes for cache misses
        let hash_results: Vec<(String, String)> = pending_hash
            .par_iter()
            .map(|(rel_path, full_path)| {
                let hash = Self::compute_md5(full_path);
                (rel_path.clone(), hash)
            })
            .filter(|(_, hash)| !hash.is_empty())
            .collect();

        // Sequential: update cache and results
        for (relative_path, file_hash) in &hash_results {
            if file_hash.is_empty() {
                continue;
            }
            // Re-check metadata (may have changed since first pass)
            let full_path = self.workspace_path.join(relative_path);
            let metadata = std::fs::metadata(&full_path).ok();
            let file_size = metadata.as_ref().map(|m| m.len() as i64).unwrap_or(0);
            let mtime_ns = metadata
                .and_then(|m| m.modified().ok())
                .and_then(|t| t.duration_since(UNIX_EPOCH).ok())
                .map(|d| d.as_nanos() as i64)
                .unwrap_or(0);

            current_files.insert(
                relative_path.clone(),
                FileState {
                    relative_path: relative_path.clone(),
                    file_hash: file_hash.clone(),
                    file_size,
                    mtime_ns,
                },
            );
            self.hash_cache.put(
                relative_path.clone(),
                HashEntry {
                    file_hash: file_hash.clone(),
                    file_size,
                    mtime_ns,
                    cached_at: now,
                },
            );
        }

        (current_files, blocked_files)
    }

    pub fn list_workspace_files(&self, ignore_patterns: &[String]) -> Vec<String> {
        self.iter_visible_files(ignore_patterns)
            .into_iter()
            .map(|(path, _)| path)
            .collect()
    }

    pub fn workspace_path(&self) -> &Path {
        &self.workspace_path
    }

    pub fn read_relative_file(&self, relative_path: &str) -> Result<Vec<u8>, String> {
        let full_path = self.workspace_path.join(relative_path);
        std::fs::read(&full_path).map_err(|e| format!("Failed to read {}: {}", relative_path, e))
    }

    pub fn restore_files(
        &self,
        version_files: &[VersionFileInfo],
        ignore_patterns: &[String],
        backup_current: bool,
    ) -> Result<(i64, i64, Vec<String>), String> {
        if backup_current {
            self.backup_current_state(ignore_patterns)?;
        }

        let desired_active: HashMap<&str, &VersionFileInfo> = version_files
            .iter()
            .filter(|f| ACTIVE_FILE_STATUSES.contains(&f.file_status.as_str()))
            .map(|f| (f.relative_path.as_str(), f))
            .collect();

        let desired_paths: std::collections::HashSet<&&str> =
            desired_active.keys().collect();
        let current_paths: std::collections::HashSet<String> =
            self.list_workspace_files(ignore_patterns).into_iter().collect();

        let mut removed_count: i64 = 0;
        let mut restored_count: i64 = 0;
        let warnings: Vec<String> = Vec::new();

        // Remove files not in target version
        for extra_path in current_paths.iter() {
            if !desired_paths.contains(&extra_path.as_str()) {
                let full_path = self.workspace_path.join(extra_path);
                if full_path.exists() {
                    std::fs::remove_file(&full_path)
                        .map_err(|e| format!("Failed to remove {}: {}", extra_path, e))?;
                    removed_count += 1;
                    self.cleanup_empty_directories(full_path.parent().unwrap());
                }
            }
        }

        // Restore files from version
        for file in version_files {
            let target_path = self.workspace_path.join(&file.relative_path);
            match file.file_status.as_str() {
                "delete" => {
                    if target_path.exists() {
                        std::fs::remove_file(&target_path)
                            .map_err(|e| format!("Failed to remove {}: {}", file.relative_path, e))?;
                        removed_count += 1;
                        self.cleanup_empty_directories(target_path.parent().unwrap());
                    }
                }
                "add" | "modify" | "unmodified" => {
                    let content = match file.file_content.as_ref() {
                        Some(bytes) => bytes.clone(),
                        None => {
                            // Try blob storage
                            let blob_path = crate::project_paths::get_blob_path(
                                &self.workspace_path, &file.file_hash
                            );
                            std::fs::read(&blob_path).map_err(|e| {
                                format!("Missing content and blob for {}: {}", file.relative_path, e)
                            })?
                        }
                    };
                    if let Some(parent) = target_path.parent() {
                        std::fs::create_dir_all(parent)
                            .map_err(|e| format!("Failed to create dir {:?}: {}", parent, e))?;
                    }
                    std::fs::write(&target_path, content)
                        .map_err(|e| format!("Failed to write {}: {}", file.relative_path, e))?;
                    restored_count += 1;
                }
                _ => {}
            }
        }

        Ok((restored_count, removed_count, warnings))
    }

    pub fn export_version_files(
        &self,
        version_files: &[VersionFileInfo],
        export_path: &Path,
    ) -> Result<bool, String> {
        for file in version_files {
            if file.file_status == "delete" {
                continue;
            }
            let content = match file.file_content.as_ref() {
                Some(bytes) => bytes.clone(),
                None => {
                    let blob_path = crate::project_paths::get_blob_path(
                        &self.workspace_path, &file.file_hash
                    );
                    std::fs::read(&blob_path).map_err(|e| {
                        format!("Missing content and blob for {}: {}", file.relative_path, e)
                    })?
                }
            };
            let target_path = export_path.join(&file.relative_path);
            if let Some(parent) = target_path.parent() {
                std::fs::create_dir_all(parent)
                    .map_err(|e| format!("Failed to create dir {:?}: {}", parent, e))?;
            }
            std::fs::write(&target_path, content)
                .map_err(|e| format!("Failed to write {}: {}", file.relative_path, e))?;
        }
        Ok(true)
    }

    fn iter_visible_files(
        &self,
        ignore_patterns: &[String],
    ) -> Vec<(String, PathBuf)> {
        let all_ignore = self.build_ignore_patterns(ignore_patterns);
        let mut results = Vec::new();

        let walker = WalkDir::new(&self.workspace_path)
            .into_iter()
            .filter_entry(|entry| {
                let relative = entry
                    .path()
                    .strip_prefix(&self.workspace_path)
                    .unwrap_or(entry.path());
                let relative_str = relative.to_string_lossy().replace('\\', "/");
                if entry.file_type().is_dir() {
                    let name = relative_str.trim_end_matches('/').to_string();
                    !self.should_ignore(&name, &all_ignore, true)
                } else {
                    true
                }
            });

        for entry in walker {
            let entry = match entry {
                Ok(e) => e,
                Err(_) => continue,
            };
            if !entry.file_type().is_file() {
                continue;
            }

            let file_path = entry.path().to_owned();
            let relative = file_path
                .strip_prefix(&self.workspace_path)
                .unwrap_or(&file_path);
            let relative_str = relative.to_string_lossy().replace('\\', "/");

            if relative_str.starts_with("..") || relative_str.contains("../") {
                continue;
            }

            if self.should_ignore(&relative_str, &all_ignore, false) {
                continue;
            }

            if results.len() >= 10_000 {
                tracing::warn!("File count exceeded limit (10000), stopping scan");
                break;
            }

            results.push((relative_str, file_path));
        }

        results
    }

    fn build_ignore_patterns(&self, extra_patterns: &[String]) -> Vec<String> {
        let mut patterns: Vec<String> = DEFAULT_IGNORE_PATTERNS
            .iter()
            .map(|s| s.to_string())
            .collect();

        patterns.extend(self.load_ignore_file());
        patterns.extend(extra_patterns.iter().cloned());
        patterns
    }

    fn load_ignore_file(&self) -> Vec<String> {
        let ignore_path = self.workspace_path.join(".vermanignore");
        let content = match std::fs::read_to_string(&ignore_path) {
            Ok(c) => c,
            Err(_) => return Vec::new(),
        };

        content
            .lines()
            .map(|line| line.trim().to_string())
            .filter(|line| !line.is_empty() && !line.starts_with('#'))
            .collect()
    }

    fn should_ignore(&self, name: &str, ignore_patterns: &[String], is_dir: bool) -> bool {
        let normalized = name.replace('\\', "/").trim().to_string();
        let normalized = normalized.strip_prefix("./").unwrap_or(&normalized).to_string();
        let normalized = normalized.trim_end_matches('/').to_string();
        let basename = Path::new(&normalized)
            .file_name()
            .map(|n| n.to_string_lossy().to_string())
            .unwrap_or_default();

        for pattern in ignore_patterns {
            let p = pattern.replace('\\', "/").trim().to_string();
            let p = p.strip_prefix("./").unwrap_or(&p).to_string();
            if p.is_empty() {
                continue;
            }

            if p.ends_with('/') {
                if !is_dir {
                    continue;
                }
                let dir_pattern = p.trim_end_matches('/');
                if normalized == dir_pattern
                    || normalized.starts_with(&format!("{}/", dir_pattern))
                    || basename == dir_pattern
                    || Self::fnmatch(&normalized, dir_pattern)
                    || Self::fnmatch(&basename, dir_pattern)
                {
                    return true;
                }
                continue;
            }

            if Self::fnmatch(&basename, &p) || Self::fnmatch(&normalized, &p) {
                return true;
            }
        }

        false
    }

    fn fnmatch(name: &str, pattern: &str) -> bool {
        if pattern.is_empty() {
            return name.is_empty();
        }

        let pattern_chars: Vec<char> = pattern.chars().collect();
        let name_chars: Vec<char> = name.chars().collect();

        Self::fnmatch_recursive(&name_chars, &pattern_chars, 0, 0)
    }

    fn fnmatch_recursive(
        name: &[char],
        pattern: &[char],
        ni: usize,
        pi: usize,
    ) -> bool {
        if pi == pattern.len() {
            return ni == name.len();
        }

        match pattern[pi] {
            '*' => {
                // Try matching zero or more characters
                if Self::fnmatch_recursive(name, pattern, ni, pi + 1) {
                    return true;
                }
                if ni < name.len()
                    && Self::fnmatch_recursive(name, pattern, ni + 1, pi)
                {
                    return true;
                }
                false
            }
            '?' => {
                if ni < name.len() {
                    Self::fnmatch_recursive(name, pattern, ni + 1, pi + 1)
                } else {
                    false
                }
            }
            '[' => {
                // Find the closing bracket
                let mut negated = false;
                if pi + 1 < pattern.len() && pattern[pi + 1] == '!' {
                    negated = true;
                }
                let mut matched = false;
                let close = pattern[pi..].iter().position(|&c| c == ']');
                if let Some(end) = close {
                    let end = pi + end;
                    let charset = &pattern[pi + 1..end];
                    // Simple bracket expression (no ranges for now)
                    if ni < name.len() {
                        matched = charset.contains(&name[ni]);
                        if negated {
                            matched = !matched;
                        }
                    }
                    if matched {
                        return Self::fnmatch_recursive(name, pattern, ni + 1, end + 1);
                    }
                    false
                } else {
                    // No closing bracket, treat as literal
                    if ni < name.len() && name[ni] == pattern[pi] {
                        Self::fnmatch_recursive(name, pattern, ni + 1, pi + 1)
                    } else {
                        false
                    }
                }
            }
            c => {
                if ni < name.len() && (name[ni] == c || (c == '/' && name[ni] == '\\')) {
                    Self::fnmatch_recursive(name, pattern, ni + 1, pi + 1)
                } else {
                    false
                }
            }
        }
    }


    fn compute_md5(file_path: &Path) -> String {
        let file = match std::fs::File::open(file_path) {
            Ok(f) => f,
            Err(e) => {
                tracing::warn!(error = %e, path = %file_path.display(), "Cannot open for hashing");
                return String::new();
            }
        };

        let metadata = match file.metadata() {
            Ok(m) => m,
            Err(_) => return String::new(),
        };
        let file_size = metadata.len();

        let chunk_size: usize = if file_size < 10 * 1024 * 1024 {
            4096
        } else {
            64 * 1024
        };

        let mut hasher = Md5::new();
        let mut reader = std::io::BufReader::with_capacity(chunk_size, file);
        let mut buffer = vec![0u8; chunk_size];

        loop {
            match reader.read(&mut buffer) {
                Ok(0) => break,
                Ok(n) => {
                    hasher.update(&buffer[..n]);
                }
                Err(e) => {
                    tracing::warn!(error = %e, path = %file_path.display(), "Hash read error");
                    return String::new();
                }
            }
        }

        format!("{:x}", hasher.finalize())
    }

    fn backup_current_state(&self, ignore_patterns: &[String]) -> Result<(), String> {
        let backup_dir = crate::project_paths::get_backup_dir(&self.workspace_path);
        let timestamp = chrono::Local::now().format("%Y%m%d_%H%M%S");
        let backup_path = backup_dir.join(format!("backup_{}", timestamp));

        std::fs::create_dir_all(&backup_path)
            .map_err(|e| format!("Failed to create backup dir: {}", e))?;

        let mut count = 0;
        for relative_path in self.list_workspace_files(ignore_patterns) {
            let source = self.workspace_path.join(&relative_path);
            let target = backup_path.join(&relative_path);
            if let Some(parent) = target.parent() {
                std::fs::create_dir_all(parent).ok();
            }
            match std::fs::copy(&source, &target) {
                Ok(_) => count += 1,
                Err(e) => tracing::warn!(error = %e, path = %relative_path, "Backup copy failed"),
            }
        }

        tracing::info!(count = count, backup = %backup_path.display(), "Backup completed");
        Ok(())
    }

    fn cleanup_empty_directories(&self, start_dir: &Path) {
        let workspace_root = &self.workspace_path;
        let mut current = start_dir.to_owned();

        loop {
            if !current.starts_with(workspace_root) {
                break;
            }
            if current == *workspace_root {
                break;
            }
            if std::fs::remove_dir(&current).is_err() {
                break;
            }
            match current.parent() {
                Some(parent) => current = parent.to_owned(),
                None => break,
            }
        }
    }
}
