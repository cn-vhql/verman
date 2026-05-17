mod commands;
mod config;
mod database;
mod file_manager;
mod file_watcher;
mod logger;
mod models;
mod project_manager;
mod project_paths;
mod version_manager;

use commands::AppState;
use std::sync::Mutex;
use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    logger::setup_tracing();

    // Handle command-line argument: path passed from context menu
    let startup_path: Option<String> = std::env::args().nth(1).and_then(|arg| {
        let path = std::path::PathBuf::from(arg);
        if !path.exists() {
            return None;
        }

        let normalized_path = if path.is_file() {
            path.parent()
                .map(std::path::Path::to_path_buf)
                .unwrap_or(path)
        } else {
            path
        };

        Some(normalized_path.to_string_lossy().to_string())
    });

    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_shell::init())
        .setup(move |app| {
            let app_handle = app.handle().clone();

            let config_manager = config::ConfigManager::new();
            let operation_logger = logger::OperationLogger::new();
            let project_manager = project_manager::ProjectManager::new();

            let app_state = AppState {
                project_manager: Mutex::new(project_manager),
                config_manager: Mutex::new(config_manager),
                operation_logger,
                app_handle: Mutex::new(Some(app_handle)),
                startup_path: Mutex::new(startup_path),
            };

            app.manage(app_state);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            // Project
            commands::create_project,
            commands::open_project,
            commands::close_project,
            commands::is_project_open,
            commands::get_project_path,
            commands::get_project_info,
            // Versions
            commands::refresh_workspace,
            commands::get_all_versions,
            commands::create_version,
            commands::rollback_to_version,
            commands::get_version_details,
            commands::compare_versions,
            commands::export_version,
            // Config
            commands::get_config,
            commands::set_ignore_patterns,
            commands::set_auto_backup,
            commands::get_recent_projects,
            commands::reset_config,
            // Logs
            commands::get_operation_logs,
            commands::clear_operation_logs,
            // Context Menu
            commands::check_context_menu_status,
            commands::install_context_menu,
            commands::uninstall_context_menu,
            // Misc
            commands::open_file_with_system,
            commands::open_version_file,
            commands::is_project_workspace,
            commands::get_startup_path,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
