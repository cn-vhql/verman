#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod models;
mod platform;
mod scanner;
mod storage;

use crate::models::{
    ExportResult, LaunchContext, OpenExternalResult, VersionDetails, VersionFilePreview,
    WorkspaceData,
};
use anyhow::{anyhow, Context, Result};
use platform::{
    get_context_menu_status as platform_context_menu_status,
    install_context_menu as platform_install_context_menu,
    uninstall_context_menu as platform_uninstall_context_menu,
};
use scanner::{
    backup_current_state, changed_blobs, cleanup_empty_directories, detect_changes, export_payload,
    load_ignore_rules_text, save_ignore_rules_text, scan_workspace,
};
use std::collections::BTreeSet;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use storage::Repository;
use tauri::State;
use tracing_subscriber::EnvFilter;

#[derive(Clone)]
struct AppState {
    startup_path: Option<String>,
}

fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env())
        .with_target(false)
        .compact()
        .init();

    tauri::Builder::default()
        .manage(AppState {
            startup_path: detect_startup_path(),
        })
        .invoke_handler(tauri::generate_handler![
            get_launch_context,
            pick_workspace,
            pick_export_directory,
            open_workspace,
            refresh_workspace,
            create_version,
            rollback_version,
            get_version_details,
            get_version_file_preview,
            open_version_file_external,
            compare_versions,
            export_version,
            save_ignore_rules,
            get_context_menu_status,
            install_context_menu,
            uninstall_context_menu
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[tauri::command]
fn get_launch_context(state: State<'_, AppState>) -> LaunchContext {
    LaunchContext {
        startup_path: state.startup_path.clone(),
    }
}

#[tauri::command]
fn pick_workspace() -> Result<Option<String>, String> {
    Ok(rfd::FileDialog::new()
        .set_title("Select VerMan workspace")
        .pick_folder()
        .map(|path| path.to_string_lossy().to_string()))
}

#[tauri::command]
fn pick_export_directory() -> Result<Option<String>, String> {
    Ok(rfd::FileDialog::new()
        .set_title("Choose export directory")
        .pick_folder()
        .map(|path| path.to_string_lossy().to_string()))
}

#[tauri::command]
fn open_workspace(path: String) -> Result<WorkspaceData, String> {
    workspace_data(PathBuf::from(path)).map_err(error_to_string)
}

#[tauri::command]
fn refresh_workspace(path: String) -> Result<WorkspaceData, String> {
    workspace_data(PathBuf::from(path)).map_err(error_to_string)
}

#[tauri::command]
fn create_version(path: String, description: String) -> Result<WorkspaceData, String> {
    let workspace = PathBuf::from(path);
    if description.trim().is_empty() {
        return Err("Version description cannot be empty".to_string());
    }

    let repo = Repository::open(&workspace).map_err(error_to_string)?;
    let current = scan_workspace(&workspace).map_err(error_to_string)?;
    let previous = repo.latest_snapshot().map_err(error_to_string)?;
    let changes = detect_changes(&current, &previous);

    if changes.is_empty() {
        return Err("No file changes were detected".to_string());
    }

    let blobs = changed_blobs(&current, &changes).map_err(error_to_string)?;
    repo.create_version(description.trim(), &current, &changes, &blobs)
        .map_err(error_to_string)?;

    workspace_data(workspace).map_err(error_to_string)
}

#[tauri::command]
fn rollback_version(
    path: String,
    version_id: i64,
    backup_current: bool,
) -> Result<WorkspaceData, String> {
    let workspace = PathBuf::from(path);
    let repo = Repository::open(&workspace).map_err(error_to_string)?;
    let payload = repo.restore_payload(version_id).map_err(error_to_string)?;

    if payload.is_empty() {
        return Err("The target version does not exist or is empty".to_string());
    }

    let current = scan_workspace(&workspace).map_err(error_to_string)?;
    if backup_current {
        backup_current_state(&workspace, &current).map_err(error_to_string)?;
    }

    let expected_paths: BTreeSet<_> = payload
        .iter()
        .map(|file| file.relative_path.clone())
        .collect();

    for file in current.values() {
        if !expected_paths.contains(&file.relative_path) && file.absolute_path.exists() {
            fs::remove_file(&file.absolute_path)
                .with_context(|| format!("Failed to delete {}", file.absolute_path.display()))
                .map_err(error_to_string)?;
        }
    }

    for file in payload {
        let target = workspace.join(&file.relative_path);
        if let Some(parent) = target.parent() {
            fs::create_dir_all(parent).map_err(error_to_string)?;
        }
        fs::write(&target, file.content)
            .with_context(|| format!("Failed to write {}", target.display()))
            .map_err(error_to_string)?;
    }

    cleanup_empty_directories(&workspace).map_err(error_to_string)?;
    workspace_data(workspace).map_err(error_to_string)
}

#[tauri::command]
fn get_version_details(path: String, version_id: i64) -> Result<VersionDetails, String> {
    let workspace = PathBuf::from(path);
    validate_workspace(&workspace).map_err(error_to_string)?;
    let repo = Repository::open(&workspace).map_err(error_to_string)?;
    repo.version_details(version_id).map_err(error_to_string)
}

#[tauri::command]
fn get_version_file_preview(
    path: String,
    version_id: i64,
    relative_path: String,
) -> Result<VersionFilePreview, String> {
    let workspace = PathBuf::from(path);
    validate_workspace(&workspace).map_err(error_to_string)?;
    let repo = Repository::open(&workspace).map_err(error_to_string)?;
    let version = repo
        .get_version_entry(version_id)
        .map_err(error_to_string)?;
    let previous = repo
        .previous_version_entry(version_id)
        .map_err(error_to_string)?;
    let diff = repo
        .version_details(version_id)
        .map_err(error_to_string)?
        .files
        .into_iter()
        .find(|entry| entry.relative_path == relative_path)
        .ok_or_else(|| format!("File {} was not found in this version", relative_path))?;

    let current_bytes = if diff.status == "delete" {
        None
    } else {
        Some(
            repo.file_bytes_for_version(version_id, &diff.relative_path)
                .map_err(error_to_string)?,
        )
    };
    let previous_bytes = previous.as_ref().and_then(|entry| {
        repo.file_bytes_for_version(entry.id, &diff.relative_path)
            .ok()
    });

    let left_label = previous
        .as_ref()
        .map(|entry| entry.version_number.clone())
        .unwrap_or_else(|| "版本前".to_string());
    let right_label = version.version_number;

    let is_text = current_bytes
        .as_deref()
        .map(is_probably_text)
        .or_else(|| previous_bytes.as_deref().map(is_probably_text))
        .unwrap_or(false);

    let note = match diff.status.as_str() {
        "add" => Some("该文件在当前版本中新增。".to_string()),
        "delete" => Some("该文件在当前版本中被删除。".to_string()),
        _ => None,
    };

    if is_text {
        let (left_text, left_note) = decode_preview(previous_bytes.as_deref());
        let (right_text, right_note) = decode_preview(current_bytes.as_deref());
        return Ok(VersionFilePreview {
            relative_path: diff.relative_path,
            status: diff.status,
            left_label,
            right_label,
            left_text,
            right_text,
            is_text: true,
            can_open_external: true,
            note: note.or(left_note).or(right_note),
        });
    }

    Ok(VersionFilePreview {
        relative_path: diff.relative_path,
        status: diff.status,
        left_label,
        right_label,
        left_text: None,
        right_text: None,
        is_text: false,
        can_open_external: current_bytes.is_some() || previous_bytes.is_some(),
        note: Some("该文件是二进制或不可直接预览的格式，请使用系统软件打开历史版本。".to_string()),
    })
}

#[tauri::command]
fn open_version_file_external(
    path: String,
    version_id: i64,
    relative_path: String,
) -> Result<OpenExternalResult, String> {
    let workspace = PathBuf::from(path);
    validate_workspace(&workspace).map_err(error_to_string)?;
    let repo = Repository::open(&workspace).map_err(error_to_string)?;

    let bytes = repo
        .file_bytes_for_version(version_id, &relative_path)
        .or_else(|_| {
            repo.previous_version_entry(version_id)?
                .map(|entry| repo.file_bytes_for_version(entry.id, &relative_path))
                .transpose()?
                .ok_or_else(|| anyhow!("No historical file payload found for {}", relative_path))
        })
        .map_err(error_to_string)?;

    let version = repo
        .get_version_entry(version_id)
        .map_err(error_to_string)?;
    let temp_root = std::env::temp_dir()
        .join("verman")
        .join("history")
        .join(version.version_number);
    let temp_path = temp_root.join(relative_path.replace('/', "\\"));
    if let Some(parent) = temp_path.parent() {
        fs::create_dir_all(parent).map_err(error_to_string)?;
    }
    fs::write(&temp_path, bytes).map_err(error_to_string)?;
    open_with_system(&temp_path).map_err(error_to_string)?;

    Ok(OpenExternalResult {
        temp_path: temp_path.to_string_lossy().to_string(),
    })
}

#[tauri::command]
fn compare_versions(
    path: String,
    left_version_id: i64,
    right_version_id: i64,
) -> Result<crate::models::VersionDiffResult, String> {
    let workspace = PathBuf::from(path);
    validate_workspace(&workspace).map_err(error_to_string)?;
    let repo = Repository::open(&workspace).map_err(error_to_string)?;
    repo.compare_versions(left_version_id, right_version_id)
        .map_err(error_to_string)
}

#[tauri::command]
fn export_version(
    path: String,
    version_id: i64,
    target_path: String,
) -> Result<ExportResult, String> {
    let workspace = PathBuf::from(path);
    validate_workspace(&workspace).map_err(error_to_string)?;
    let repo = Repository::open(&workspace).map_err(error_to_string)?;
    let payload = repo.restore_payload(version_id).map_err(error_to_string)?;

    if payload.is_empty() {
        return Err("There are no files to export for this version".to_string());
    }

    let target = PathBuf::from(target_path);
    let file_count = export_payload(&target, &payload).map_err(error_to_string)?;
    Ok(ExportResult {
        target_path: target.to_string_lossy().to_string(),
        file_count,
    })
}

#[tauri::command]
fn save_ignore_rules(path: String, contents: String) -> Result<WorkspaceData, String> {
    let workspace = PathBuf::from(path);
    validate_workspace(&workspace).map_err(error_to_string)?;
    save_ignore_rules_text(&workspace, &contents).map_err(error_to_string)?;
    workspace_data(workspace).map_err(error_to_string)
}

#[tauri::command]
fn get_context_menu_status() -> crate::models::ContextMenuStatus {
    platform_context_menu_status()
}

#[tauri::command]
fn install_context_menu() -> Result<crate::models::ContextMenuStatus, String> {
    platform_install_context_menu().map_err(error_to_string)
}

#[tauri::command]
fn uninstall_context_menu() -> Result<crate::models::ContextMenuStatus, String> {
    platform_uninstall_context_menu().map_err(error_to_string)
}

fn workspace_data(workspace: PathBuf) -> Result<WorkspaceData> {
    validate_workspace(&workspace)?;
    let repo = Repository::open(&workspace)?;
    let current = scan_workspace(&workspace)?;
    let previous = repo.latest_snapshot()?;
    let changes = detect_changes(&current, &previous);
    let versions = repo.list_versions()?;
    let ignore_rules = load_ignore_rules_text(&workspace)?;

    Ok(WorkspaceData {
        workspace_path: workspace.to_string_lossy().to_string(),
        total_files: current.len(),
        total_versions: versions.len(),
        changed_files: changes.len(),
        changes,
        versions,
        ignore_rules,
    })
}

fn validate_workspace(workspace: &Path) -> Result<()> {
    if workspace.as_os_str().is_empty() {
        return Err(anyhow!("Workspace path cannot be empty"));
    }

    if !workspace.exists() {
        return Err(anyhow!("Workspace does not exist: {}", workspace.display()));
    }

    if !workspace.is_dir() {
        return Err(anyhow!(
            "Selected path is not a directory: {}",
            workspace.display()
        ));
    }

    Ok(())
}

fn detect_startup_path() -> Option<String> {
    let mut args = std::env::args_os();
    let _ = args.next();
    let candidate = args.next()?;
    let path = PathBuf::from(candidate);
    if path.exists() && path.is_dir() {
        Some(path.to_string_lossy().to_string())
    } else {
        None
    }
}

fn error_to_string(error: impl std::fmt::Display) -> String {
    error.to_string()
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
    let note = truncated.then(|| "预览内容已截断，只显示前 200 KB。".to_string());
    (Some(text), note)
}

fn open_with_system(path: &Path) -> Result<()> {
    #[cfg(target_os = "windows")]
    {
        Command::new("cmd")
            .args(["/C", "start", "", path.to_string_lossy().as_ref()])
            .spawn()
            .context("Failed to launch file with Windows shell")?;
        return Ok(());
    }

    #[cfg(target_os = "macos")]
    {
        Command::new("open")
            .arg(path)
            .spawn()
            .context("Failed to launch file with macOS open")?;
        return Ok(());
    }

    #[cfg(target_os = "linux")]
    {
        Command::new("xdg-open")
            .arg(path)
            .spawn()
            .context("Failed to launch file with xdg-open")?;
        return Ok(());
    }

    #[allow(unreachable_code)]
    Err(anyhow!(
        "Opening historical files is not supported on this platform"
    ))
}
