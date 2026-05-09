use std::collections::{HashMap, HashSet};
use std::path::Path;
use std::sync::Mutex;
use std::time::{SystemTime, UNIX_EPOCH};

use crate::database::DatabaseManager;
use crate::file_manager::FileManager;
use crate::models::{
    BLOB_STORAGE_THRESHOLD, ChangeEntry, CreateVersionResult, DiffEntry, DiffFileEntry, DiffSide,
    FileState, ProgressPayload, RollbackResult, ScanSnapshot, VersionDetails, VersionDiff,
    VersionFileInfo, VersionInfo, VersionStatistics,
};

pub struct VersionManager {
    pub db_manager: DatabaseManager,
    pub file_manager: Mutex<FileManager>,
    config_ignore_patterns: Vec<String>,
    last_scan_snapshot: Mutex<Option<ScanSnapshot>>,
    last_scan_time: Mutex<f64>,
}

#[allow(dead_code)]
impl VersionManager {
    pub fn new(
        db_manager: DatabaseManager,
        file_manager: FileManager,
        config_ignore_patterns: Vec<String>,
    ) -> Self {
        Self {
            db_manager,
            file_manager: Mutex::new(file_manager),
            config_ignore_patterns,
            last_scan_snapshot: Mutex::new(None),
            last_scan_time: Mutex::new(0.0),
        }
    }

    pub fn refresh_workspace(&self, force: bool) -> Result<ScanSnapshot, String> {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_secs_f64())
            .unwrap_or(0.0);

        if !force {
            if let Ok(last_time) = self.last_scan_time.lock() {
                if *last_time > 0.0 && now - *last_time < 1.0 {
                    if let Ok(snapshot) = self.last_scan_snapshot.lock() {
                        if let Some(ref snap) = *snapshot {
                            return Ok(snap.clone());
                        }
                    }
                }
            }
        }

        let indexed_files = self.db_manager.get_workspace_index();

        let mut fm = self.file_manager.lock().map_err(|e| e.to_string())?;
        let (current_files, blocked_files) =
            fm.scan_workspace(&self.config_ignore_patterns, &indexed_files);
        let scan_id = now as i64 * 1_000_000_000;

        let file_states: Vec<FileState> = current_files.values().cloned().collect();
        self.db_manager
            .update_workspace_index(&file_states, scan_id)?;

        let latest_version_hashes = self.get_latest_version_hashes();
        let blocked_paths: HashSet<&str> = blocked_files
            .iter()
            .map(|b| b.relative_path.as_str())
            .collect();
        let changes = Self::detect_changes(
            &current_files,
            &latest_version_hashes,
            &blocked_paths,
        );

        let snapshot = ScanSnapshot {
            current_files,
            changes,
            blocked_files,
            scan_id,
        };

        if let Ok(mut snap) = self.last_scan_snapshot.lock() {
            *snap = Some(snapshot.clone());
        }
        if let Ok(mut t) = self.last_scan_time.lock() {
            *t = now;
        }

        Ok(snapshot)
    }

    pub fn get_current_changes(&self) -> Result<Vec<ChangeEntry>, String> {
        let snapshot = self.refresh_workspace(false)?;
        Ok(snapshot.changes)
    }

    pub fn create_version(
        &self,
        description: &str,
        scan_snapshot: Option<ScanSnapshot>,
    ) -> CreateVersionResult {
        self.create_version_with_progress(description, scan_snapshot, None)
    }

    pub fn create_version_with_progress(
        &self,
        description: &str,
        scan_snapshot: Option<ScanSnapshot>,
        on_progress: Option<&dyn Fn(ProgressPayload)>,
    ) -> CreateVersionResult {
        let snapshot = match scan_snapshot {
            Some(s) => s,
            None => match self.refresh_workspace(true) {
                Ok(s) => s,
                Err(e) => {
                    return CreateVersionResult {
                        error: Some(format!("Refresh failed: {}", e)),
                        ..Default::default()
                    }
                }
            },
        };

        if snapshot.changes.is_empty() {
            return CreateVersionResult {
                error: Some("没有检测到文件变更。".to_string()),
                ..Default::default()
            };
        }

        tracing::info!("开始创建版本...");

        let previous_hashes = self.get_latest_version_hashes();
        let version_files = self.prepare_version_files(&snapshot.current_files, &previous_hashes, &snapshot.changes);

        let version_number = self.generate_version_number();
        let version_id = match self.db_manager.create_version(
            &version_number,
            description,
            snapshot.changes.len() as i64,
        ) {
            Ok(id) => id,
            Err(e) => {
                return CreateVersionResult {
                    error: Some(e),
                    ..Default::default()
                }
            }
        };

        // Save in batches of 100
        let total_files = version_files.len();
        for (i, chunk) in version_files.chunks(100).enumerate() {
            if let Some(cb) = on_progress {
                let current = (i * 100 + chunk.len()).min(total_files);
                cb(ProgressPayload {
                    stage: "save".to_string(),
                    current,
                    total: total_files,
                    message: format!("保存中... {}/{}", current, total_files),
                });
            }
            let replace = chunk.as_ptr() == version_files.as_ptr();
            if let Err(e) = self.db_manager.save_files(version_id, chunk, replace) {
                return CreateVersionResult {
                    error: Some(e),
                    ..Default::default()
                }
            }
        }

        if let Some(cb) = on_progress {
            cb(ProgressPayload {
                stage: "done".to_string(),
                current: total_files,
                total: total_files,
                message: "版本创建完成".to_string(),
            });
        }

        self.clear_scan_cache();

        tracing::info!(version = %version_number, count = snapshot.changes.len(), "版本创建成功");

        CreateVersionResult {
            success: true,
            version_number: Some(version_number),
            change_count: snapshot.changes.len() as i64,
            ..Default::default()
        }
    }

    pub fn rollback_to_version(
        &self,
        version_id: i64,
        backup_current: bool,
    ) -> RollbackResult {
        self.rollback_to_version_with_progress(version_id, backup_current, None)
    }

    pub fn rollback_to_version_with_progress(
        &self,
        version_id: i64,
        backup_current: bool,
        on_progress: Option<&dyn Fn(ProgressPayload)>,
    ) -> RollbackResult {
        let version_files = match self
            .db_manager
            .get_effective_version_files(version_id, true)
        {
            Ok(files) => files,
            Err(e) => {
                return RollbackResult {
                    error: Some(e),
                    ..Default::default()
                }
            }
        };

        if version_files.is_empty() {
            return RollbackResult {
                error: Some("版本文件不存在。".to_string()),
                ..Default::default()
            };
        }

        if let Some(cb) = on_progress {
            cb(ProgressPayload {
                stage: "restore".to_string(),
                current: 0,
                total: version_files.len(),
                message: format!("正在恢复 {} 个文件...", version_files.len()),
            });
        }

        let fm = match self.file_manager.lock() {
            Ok(f) => f,
            Err(e) => {
                return RollbackResult {
                    error: Some(e.to_string()),
                    ..Default::default()
                }
            }
        };

        let result = fm.restore_files(
            &version_files,
            &self.config_ignore_patterns,
            backup_current,
        );

        let (restored_count, removed_count, warnings) = match result {
            Ok(r) => r,
            Err(e) => {
                return RollbackResult {
                    error: Some(e),
                    ..Default::default()
                }
            }
        };

        self.clear_scan_cache();
        tracing::info!(version_id = version_id, "成功回滚");

        if let Some(cb) = on_progress {
            cb(ProgressPayload {
                stage: "done".to_string(),
                current: version_files.len(),
                total: version_files.len(),
                message: "回滚完成".to_string(),
            });
        }

        RollbackResult {
            success: true,
            restored_count,
            removed_count,
            warnings,
            ..Default::default()
        }
    }

    pub fn get_all_versions(&self) -> Result<Vec<VersionInfo>, String> {
        self.db_manager.get_all_versions()
    }

    pub fn get_version_details(&self, version_id: i64) -> Option<VersionDetails> {
        let versions = self.db_manager.get_all_versions().ok()?;
        let version = versions.into_iter().find(|v| v.id == version_id)?;

        let files = self
            .db_manager
            .get_effective_version_files(version_id, true)
            .ok()?;

        let add_count = files.iter().filter(|f| f.file_status == "add").count();
        let modify_count = files.iter().filter(|f| f.file_status == "modify").count();
        let delete_count = files.iter().filter(|f| f.file_status == "delete").count();
        let unmodified_count = files.iter().filter(|f| f.file_status == "unmodified").count();

        Some(VersionDetails {
            id: version.id,
            version_number: version.version_number,
            create_time: version.create_time,
            description: version.description,
            change_count: version.change_count,
            files,
            statistics: VersionStatistics {
                add_count,
                modify_count,
                delete_count,
                unmodified_count,
                total_count: add_count + modify_count + delete_count + unmodified_count,
            },
        })
    }

    pub fn compare_versions(&self, id1: i64, id2: i64) -> Result<VersionDiff, String> {
        let files1 = self
            .db_manager
            .get_effective_version_files(id1, false)?;
        let files2 = self
            .db_manager
            .get_effective_version_files(id2, false)?;
        Ok(Self::compare_versions_effective(&files1, &files2))
    }

    pub fn export_version(&self, version_id: i64, export_path: &Path) -> Result<bool, String> {
        self.export_version_with_progress(version_id, export_path, None)
    }

    pub fn export_version_with_progress(
        &self,
        version_id: i64,
        export_path: &Path,
        on_progress: Option<&dyn Fn(ProgressPayload)>,
    ) -> Result<bool, String> {
        let version_files = self
            .db_manager
            .get_effective_version_files(version_id, true)?;
        if version_files.is_empty() {
            return Ok(false);
        }

        if let Some(cb) = on_progress {
            cb(ProgressPayload {
                stage: "export".to_string(),
                current: 0,
                total: version_files.len(),
                message: format!("正在导出 {} 个文件...", version_files.len()),
            });
        }

        let fm = self.file_manager.lock().map_err(|e| e.to_string())?;
        let result = fm.export_version_files(&version_files, export_path)?;

        if let Some(cb) = on_progress {
            cb(ProgressPayload {
                stage: "done".to_string(),
                current: version_files.len(),
                total: version_files.len(),
                message: "导出完成".to_string(),
            });
        }

        Ok(result)
    }

    pub fn delete_version(&self, version_id: i64) -> Result<(), String> {
        self.db_manager.delete_version(version_id)
    }

    // ── Private Helpers ──

    fn get_latest_version_hashes(&self) -> HashMap<String, String> {
        self.db_manager
            .get_latest_version_id()
            .map(|id| self.db_manager.get_version_file_hashes(id))
            .unwrap_or_default()
    }

    fn detect_changes(
        current_files: &HashMap<String, FileState>,
        previous_files: &HashMap<String, String>,
        blocked_paths: &HashSet<&str>,
    ) -> Vec<ChangeEntry> {
        let mut changes = Vec::new();
        let current_set: HashSet<&str> =
            current_files.keys().map(|s| s.as_str()).collect();
        let previous_set: HashSet<&str> =
            previous_files.keys().map(|s| s.as_str()).collect();

        // New files
        for path in difference(&current_set, &previous_set) {
            if path.starts_with(".verman") {
                continue;
            }
            if let Some(state) = current_files.get(path) {
                changes.push(ChangeEntry {
                    relative_path: path.to_string(),
                    file_hash: state.file_hash.clone(),
                    file_status: "add".to_string(),
                });
            }
        }

        // Modified files
        for path in intersection(&current_set, &previous_set) {
            if let Some(state) = current_files.get(path) {
                if let Some(prev_hash) = previous_files.get(path) {
                    if state.file_hash != *prev_hash {
                        changes.push(ChangeEntry {
                            relative_path: path.to_string(),
                            file_hash: state.file_hash.clone(),
                            file_status: "modify".to_string(),
                        });
                    }
                }
            }
        }

        // Deleted files
        for path in difference(&previous_set, &current_set) {
            if path.starts_with(".verman") || blocked_paths.contains(path) {
                continue;
            }
            changes.push(ChangeEntry {
                relative_path: path.to_string(),
                file_hash: previous_files.get(path).cloned().unwrap_or_default(),
                file_status: "delete".to_string(),
            });
        }

        changes.sort_by(|a, b| a.relative_path.cmp(&b.relative_path));
        changes
    }

    fn prepare_version_files(
        &self,
        current_files: &HashMap<String, FileState>,
        previous_hashes: &HashMap<String, String>,
        changes: &[ChangeEntry],
    ) -> Vec<VersionFileInfo> {
        let mut status_map: HashMap<&str, (&str, &str)> = HashMap::new();

        for change in changes {
            status_map.insert(
                change.relative_path.as_str(),
                (change.file_status.as_str(), change.file_hash.as_str()),
            );
        }

        for (path, state) in current_files {
            if !status_map.contains_key(path.as_str()) {
                let status = if previous_hashes.get(path) == Some(&state.file_hash) {
                    "unmodified"
                } else {
                    "add"
                };
                status_map.insert(path.as_str(), (status, state.file_hash.as_str()));
            }
        }

        let mut result: Vec<VersionFileInfo> = Vec::new();
        let mut paths: Vec<&&str> = status_map.keys().collect();
        paths.sort();

        for path in paths {
            let (status, hash) = status_map[path];
            let content = match status {
                "add" | "modify" => {
                    let fm = self.file_manager.lock().ok();
                    let full_path = fm.as_ref().map(|f| f.workspace_path().join(path));
                    let file_size = full_path.as_ref()
                        .and_then(|p| std::fs::metadata(p).ok())
                        .map(|m| m.len() as i64)
                        .unwrap_or(0);

                    if file_size > BLOB_STORAGE_THRESHOLD {
                        // Store large file as external blob
                        if let Some(ref f) = fm {
                            if let Ok(bytes) = f.read_relative_file(path) {
                                let blob_path = crate::project_paths::get_blob_path(
                                    f.workspace_path(), hash
                                );
                                std::fs::create_dir_all(blob_path.parent().unwrap()).ok();
                                std::fs::write(&blob_path, &bytes).ok();
                            }
                        }
                        None
                    } else {
                        fm.and_then(|f| f.read_relative_file(path).ok())
                    }
                }
                _ => None,
            };

            result.push(VersionFileInfo {
                relative_path: path.to_string(),
                file_hash: hash.to_string(),
                file_status: status.to_string(),
                file_content: content,
            });
        }

        result
    }

    fn generate_version_number(&self) -> String {
        let versions = match self.db_manager.get_all_versions() {
            Ok(v) => v,
            Err(_) => return format!("v{}", SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .map(|d| d.as_secs())
                .unwrap_or(0)),
        };

        if versions.is_empty() {
            return "v1.0".to_string();
        }

        let latest = &versions[0].version_number;
        if let Some(v_str) = latest.strip_prefix('v') {
            if let Some((major, minor)) = v_str.split_once('.') {
                if let (Ok(m), Ok(n)) = (major.parse::<i64>(), minor.parse::<i64>()) {
                    let candidate = format!("v{}.{}", m, n + 1);
                    if !versions.iter().any(|v| v.version_number == candidate) {
                        return candidate;
                    }
                }
            }
        }

        let base = chrono::Local::now().format("v%Y%m%d_%H%M%S").to_string();
        let existing: HashSet<&str> =
            versions.iter().map(|v| v.version_number.as_str()).collect();
        if !existing.contains(base.as_str()) {
            return base;
        }
        let mut counter = 1;
        loop {
            let candidate = format!("{}_{}", base, counter);
            if !existing.contains(candidate.as_str()) {
                return candidate;
            }
            counter += 1;
        }
    }

    fn clear_scan_cache(&self) {
        if let Ok(mut snap) = self.last_scan_snapshot.lock() {
            *snap = None;
        }
        if let Ok(mut t) = self.last_scan_time.lock() {
            *t = 0.0;
        }
        if let Ok(mut fm) = self.file_manager.lock() {
            fm.clear_hash_cache();
        }
    }

    fn compare_versions_effective(
        files1: &[VersionFileInfo],
        files2: &[VersionFileInfo],
    ) -> VersionDiff {
        let map1: HashMap<&str, &VersionFileInfo> = files1
            .iter()
            .filter(|f| f.file_status != "delete")
            .map(|f| (f.relative_path.as_str(), f))
            .collect();
        let map2: HashMap<&str, &VersionFileInfo> = files2
            .iter()
            .filter(|f| f.file_status != "delete")
            .map(|f| (f.relative_path.as_str(), f))
            .collect();

        let set1: HashSet<&str> = map1.keys().copied().collect();
        let set2: HashSet<&str> = map2.keys().copied().collect();

        let mut only_in_first: Vec<DiffFileEntry> = set1
            .difference(&set2)
            .map(|p| {
                let f = map1[p];
                DiffFileEntry {
                    relative_path: f.relative_path.clone(),
                    file_hash: f.file_hash.clone(),
                    file_status: f.file_status.clone(),
                }
            })
            .collect();

        let mut only_in_second: Vec<DiffFileEntry> = set2
            .difference(&set1)
            .map(|p| {
                let f = map2[p];
                DiffFileEntry {
                    relative_path: f.relative_path.clone(),
                    file_hash: f.file_hash.clone(),
                    file_status: f.file_status.clone(),
                }
            })
            .collect();

        let mut different: Vec<DiffEntry> = Vec::new();
        for path in set1.intersection(&set2) {
            let f1 = map1[path];
            let f2 = map2[path];
            if f1.file_hash != f2.file_hash || f1.file_status != f2.file_status {
                different.push(DiffEntry {
                    relative_path: f1.relative_path.clone(),
                    file_in_v1: DiffSide {
                        file_hash: f1.file_hash.clone(),
                        file_status: f1.file_status.clone(),
                    },
                    file_in_v2: DiffSide {
                        file_hash: f2.file_hash.clone(),
                        file_status: f2.file_status.clone(),
                    },
                });
            }
        }

        only_in_first.sort_by(|a, b| a.relative_path.cmp(&b.relative_path));
        only_in_second.sort_by(|a, b| a.relative_path.cmp(&b.relative_path));

        VersionDiff {
            only_in_first: if only_in_first.is_empty() { None } else { Some(only_in_first) },
            only_in_second: if only_in_second.is_empty() { None } else { Some(only_in_second) },
            different: if different.is_empty() { None } else { Some(different) },
        }
    }
}

// Set operation helpers
fn difference<'a>(a: &HashSet<&'a str>, b: &HashSet<&'a str>) -> Vec<&'a str> {
    let mut result: Vec<&str> = a.difference(b).copied().collect();
    result.sort();
    result
}

fn intersection<'a>(a: &HashSet<&'a str>, b: &HashSet<&'a str>) -> Vec<&'a str> {
    let mut result: Vec<&str> = a.intersection(b).copied().collect();
    result.sort();
    result
}