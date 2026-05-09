use std::path::Path;
use std::sync::Mutex;

use tauri::State;
use tauri::Emitter;

use crate::config::{AppConfig, ConfigManager};
use crate::logger::OperationLogger;
use crate::models::*;
use crate::project_manager::ProjectManager;

pub struct AppState {
    pub project_manager: Mutex<ProjectManager>,
    pub config_manager: Mutex<ConfigManager>,
    pub operation_logger: OperationLogger,
    pub app_handle: Mutex<Option<tauri::AppHandle>>,
}

// ── Project Commands ──

#[tauri::command]
pub fn create_project(
    state: State<'_, AppState>,
    workspace_path: String,
) -> Result<bool, String> {
    let config = state.config_manager.lock().map_err(|e| e.to_string())?;
    let ignore_patterns = config.get_ignore_patterns();
    drop(config);

    let mut pm = state.project_manager.lock().map_err(|e| e.to_string())?;
    let result = pm.create_project(Path::new(&workspace_path), ignore_patterns)?;

    if result {
        if let Some(ah) = state.app_handle.lock().map_err(|e| e.to_string())?.clone() {
            pm.start_watcher(Path::new(&workspace_path), ah);
        }
        let mut config = state.config_manager.lock().map_err(|e| e.to_string())?;
        config.add_recent_project(&workspace_path);
        state
            .operation_logger
            .log_operation("创建项目", &workspace_path, &workspace_path, "INFO");
    }

    Ok(result)
}

#[tauri::command]
pub fn open_project(
    state: State<'_, AppState>,
    workspace_path: String,
) -> Result<bool, String> {
    let config = state.config_manager.lock().map_err(|e| e.to_string())?;
    let ignore_patterns = config.get_ignore_patterns();
    drop(config);

    let mut pm = state.project_manager.lock().map_err(|e| e.to_string())?;
    let result = pm.open_project(Path::new(&workspace_path), ignore_patterns)?;

    if result {
        if let Some(ah) = state.app_handle.lock().map_err(|e| e.to_string())?.clone() {
            pm.start_watcher(Path::new(&workspace_path), ah);
        }
        let mut config = state.config_manager.lock().map_err(|e| e.to_string())?;
        config.add_recent_project(&workspace_path);
        state
            .operation_logger
            .log_operation("打开项目", &workspace_path, &workspace_path, "INFO");
    }

    Ok(result)
}

#[tauri::command]
pub fn close_project(state: State<'_, AppState>) -> Result<(), String> {
    let mut pm = state.project_manager.lock().map_err(|e| e.to_string())?;
    let path = pm.get_project_path().map(|p| p.to_string_lossy().to_string());
    pm.close();
    if let Some(p) = path {
        state
            .operation_logger
            .log_operation("关闭项目", "", &p, "INFO");
    }
    Ok(())
}

#[tauri::command]
pub fn is_project_open(state: State<'_, AppState>) -> Result<bool, String> {
    let pm = state.project_manager.lock().map_err(|e| e.to_string())?;
    Ok(pm.is_open())
}

#[tauri::command]
pub fn get_project_path(state: State<'_, AppState>) -> Result<Option<String>, String> {
    let pm = state.project_manager.lock().map_err(|e| e.to_string())?;
    Ok(pm.get_project_path().map(|p| p.to_string_lossy().to_string()))
}

#[tauri::command]
pub fn get_project_info(state: State<'_, AppState>) -> Result<Option<ProjectInfo>, String> {
    let pm = state.project_manager.lock().map_err(|e| e.to_string())?;
    let vm = match &pm.version_manager {
        Some(v) => v,
        None => return Ok(None),
    };

    let versions = vm.get_all_versions()?;
    let (project_path, create_time) = vm
        .db_manager
        .get_project_info()
        .unwrap_or_else(|| ("".to_string(), "".to_string()));

    let (latest_version, latest_time) = versions
        .first()
        .map(|v| (v.version_number.clone(), v.create_time.clone()))
        .unwrap_or_else(|| ("无".to_string(), "无".to_string()));

    Ok(Some(ProjectInfo {
        project_path,
        create_time,
        version_count: versions.len() as i64,
        latest_version,
        latest_time,
    }))
}

// ── Version Commands ──

#[tauri::command]
pub fn refresh_workspace(state: State<'_, AppState>, force: bool) -> Result<ScanSnapshot, String> {
    let pm = state.project_manager.lock().map_err(|e| e.to_string())?;
    let vm = pm.version_manager.as_ref().ok_or("No open project")?;
    vm.refresh_workspace(force)
}

#[tauri::command]
pub fn get_all_versions(state: State<'_, AppState>) -> Result<Vec<VersionInfo>, String> {
    let pm = state.project_manager.lock().map_err(|e| e.to_string())?;
    let vm = pm.version_manager.as_ref().ok_or("No open project")?;
    vm.get_all_versions()
}

#[tauri::command]
pub fn create_version(
    state: State<'_, AppState>,
    description: String,
    snapshot_json: String,
) -> Result<CreateVersionResult, String> {
    let snapshot: Option<ScanSnapshot> = if snapshot_json.is_empty() {
        None
    } else {
        serde_json::from_str(&snapshot_json).ok()
    };

    let progress_cb: Option<Box<dyn Fn(ProgressPayload)>> = state
        .app_handle
        .lock()
        .map_err(|e| e.to_string())?
        .clone()
        .map(|handle| -> Box<dyn Fn(ProgressPayload)> {
            Box::new(move |p: ProgressPayload| {
                let _ = handle.emit("verman:progress", p);
            })
        });

    let pm = state.project_manager.lock().map_err(|e| e.to_string())?;
    let vm = pm.version_manager.as_ref().ok_or("No open project")?;

    let result = vm.create_version_with_progress(&description, snapshot, progress_cb.as_deref());

    if result.success {
        let path = pm
            .get_project_path()
            .map(|p| p.to_string_lossy().to_string())
            .unwrap_or_default();
        state.operation_logger.log_operation(
            "创建版本",
            &format!("版本号: {}, 变更数: {}", result.version_number.as_deref().unwrap_or("?"), result.change_count),
            &path,
            "INFO",
        );
    }

    Ok(result)
}

#[tauri::command]
pub fn rollback_to_version(
    state: State<'_, AppState>,
    version_id: i64,
    backup_current: bool,
) -> Result<RollbackResult, String> {
    let progress_cb: Option<Box<dyn Fn(ProgressPayload)>> = state
        .app_handle
        .lock()
        .map_err(|e| e.to_string())?
        .clone()
        .map(|handle| -> Box<dyn Fn(ProgressPayload)> {
            Box::new(move |p: ProgressPayload| {
                let _ = handle.emit("verman:progress", p);
            })
        });

    let pm = state.project_manager.lock().map_err(|e| e.to_string())?;
    let vm = pm.version_manager.as_ref().ok_or("No open project")?;
    let result = vm.rollback_to_version_with_progress(version_id, backup_current, progress_cb.as_deref());

    if result.success {
        let path = pm
            .get_project_path()
            .map(|p| p.to_string_lossy().to_string())
            .unwrap_or_default();
        state.operation_logger.log_operation(
            "回滚版本",
            &format!("版本ID: {}, 备份: {}", version_id, backup_current),
            &path,
            "WARNING",
        );
    }

    Ok(result)
}

#[tauri::command]
pub fn get_version_details(
    state: State<'_, AppState>,
    version_id: i64,
) -> Result<Option<VersionDetails>, String> {
    let pm = state.project_manager.lock().map_err(|e| e.to_string())?;
    let vm = pm.version_manager.as_ref().ok_or("No open project")?;
    Ok(vm.get_version_details(version_id))
}

#[tauri::command]
pub fn compare_versions(
    state: State<'_, AppState>,
    version_id1: i64,
    version_id2: i64,
) -> Result<VersionDiff, String> {
    let pm = state.project_manager.lock().map_err(|e| e.to_string())?;
    let vm = pm.version_manager.as_ref().ok_or("No open project")?;
    vm.compare_versions(version_id1, version_id2)
}

#[tauri::command]
pub fn export_version(
    state: State<'_, AppState>,
    version_id: i64,
    export_path: String,
) -> Result<bool, String> {
    let progress_cb: Option<Box<dyn Fn(ProgressPayload)>> = state
        .app_handle
        .lock()
        .map_err(|e| e.to_string())?
        .clone()
        .map(|handle| -> Box<dyn Fn(ProgressPayload)> {
            Box::new(move |p: ProgressPayload| {
                let _ = handle.emit("verman:progress", p);
            })
        });

    let pm = state.project_manager.lock().map_err(|e| e.to_string())?;
    let vm = pm.version_manager.as_ref().ok_or("No open project")?;
    let result = vm.export_version_with_progress(version_id, Path::new(&export_path), progress_cb.as_deref())?;

    if result {
        let path = pm
            .get_project_path()
            .map(|p| p.to_string_lossy().to_string())
            .unwrap_or_default();
        state.operation_logger.log_operation(
            "导出版本",
            &format!("版本ID: {}, 导出到: {}", version_id, export_path),
            &path,
            "INFO",
        );
    }

    Ok(result)
}

// ── Config Commands ──

#[tauri::command]
pub fn get_config(state: State<'_, AppState>) -> Result<AppConfig, String> {
    let config = state.config_manager.lock().map_err(|e| e.to_string())?;
    Ok(config.get_config().clone())
}

#[tauri::command]
pub fn set_ignore_patterns(
    state: State<'_, AppState>,
    patterns: Vec<String>,
) -> Result<(), String> {
    let mut config = state.config_manager.lock().map_err(|e| e.to_string())?;
    config.set_ignore_patterns(patterns);
    Ok(())
}

#[tauri::command]
pub fn set_auto_backup(state: State<'_, AppState>, enabled: bool) -> Result<(), String> {
    let mut config = state.config_manager.lock().map_err(|e| e.to_string())?;
    config.set_auto_backup(enabled);
    Ok(())
}

#[tauri::command]
pub fn get_recent_projects(state: State<'_, AppState>) -> Result<Vec<String>, String> {
    let config = state.config_manager.lock().map_err(|e| e.to_string())?;
    Ok(config.get_recent_projects().to_vec())
}

#[tauri::command]
pub fn reset_config(state: State<'_, AppState>) -> Result<(), String> {
    let mut config = state.config_manager.lock().map_err(|e| e.to_string())?;
    config.reset_to_defaults();
    Ok(())
}

// ── Log Commands ──

#[tauri::command]
pub fn get_operation_logs(state: State<'_, AppState>) -> Result<Vec<LogEntry>, String> {
    Ok(state.operation_logger.get_logs())
}

#[tauri::command]
pub fn clear_operation_logs(state: State<'_, AppState>) -> Result<(), String> {
    state.operation_logger.clear_logs();
    Ok(())
}

// ── Context Menu Commands ──

#[tauri::command]
pub fn check_context_menu_status() -> Result<i32, String> {
    #[cfg(target_os = "windows")]
    {
        use winreg::enums::*;
        use winreg::RegKey;

        let keys = [
            r"Directory\Background\shell\VerMan",
            r"Directory\shell\VerMan",
            r"*\shell\VerMan",
        ];

        let mut count = 0;
        for key_path in &keys {
            match RegKey::predef(HKEY_CLASSES_ROOT).open_subkey(key_path) {
                Ok(_) => count += 1,
                Err(_) => {}
            }
        }
        Ok(count)
    }

    #[cfg(not(target_os = "windows"))]
    {
        Ok(0)
    }
}

#[tauri::command]
pub fn install_context_menu(exe_path: String) -> Result<bool, String> {
    #[cfg(target_os = "windows")]
    {
        use winreg::enums::*;
        use winreg::RegKey;

        let entries: [(&str, &str); 3] = [
            (r"Directory\Background\shell\VerMan", "%V"),
            (r"Directory\shell\VerMan", "%1"),
            (r"*\shell\VerMan", "%1"),
        ];

        for (key_path, arg) in &entries {
            let key = RegKey::predef(HKEY_CLASSES_ROOT)
                .create_subkey(key_path)
                .map_err(|e| format!("Failed to create registry key: {}", e))?;
            key.0
                .set_value("", &"使用VerMan版本管理")
                .map_err(|e| format!("Failed to set value: {}", e))?;

            let cmd_key = key
                .0
                .create_subkey("command")
                .map_err(|e| format!("Failed to create command key: {}", e))?;
            cmd_key
                .0
                .set_value("", &format!("\"{}\" \"{}\"", exe_path, arg))
                .map_err(|e| format!("Failed to set command: {}", e))?;
        }

        Ok(true)
    }

    #[cfg(not(target_os = "windows"))]
    {
        let _ = exe_path;
        Err("Context menu is only supported on Windows".to_string())
    }
}

#[tauri::command]
pub fn uninstall_context_menu() -> Result<bool, String> {
    #[cfg(target_os = "windows")]
    {
        use winreg::enums::*;
        use winreg::RegKey;

        let keys = [
            r"Directory\Background\shell\VerMan",
            r"Directory\shell\VerMan",
            r"*\shell\VerMan",
        ];

        for key_path in &keys {
            // Delete command subkey first
            match RegKey::predef(HKEY_CLASSES_ROOT).open_subkey_with_flags(key_path, KEY_WRITE) {
                Ok(key) => {
                    key.delete_subkey("command").ok();
                }
                Err(_) => {}
            }
            // Delete the main key
            match winreg::RegKey::predef(HKEY_CLASSES_ROOT)
                .open_subkey_with_flags(key_path.trim_end_matches('\\'), KEY_WRITE)
            {
                Ok(parent) => {
                    let name = key_path.rsplit('\\').next().unwrap_or(key_path);
                    parent.delete_subkey(name).ok();
                }
                Err(_) => {}
            }
        }

        Ok(true)
    }

    #[cfg(not(target_os = "windows"))]
    {
        Err("Context menu is only supported on Windows".to_string())
    }
}

// ── Misc Commands ──

#[tauri::command]
pub fn open_file_with_system(path: String) -> Result<(), String> {
    open::that(&path).map_err(|e| format!("Failed to open file: {}", e))
}

#[tauri::command]
pub fn is_project_workspace(path: String) -> bool {
    crate::project_paths::is_project_workspace(Path::new(&path))
}
