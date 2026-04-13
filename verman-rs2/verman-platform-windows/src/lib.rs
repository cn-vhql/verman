use anyhow::Result;
use verman_core::ContextMenuStatus;

pub fn install_explorer_integration() -> Result<ContextMenuStatus> {
    Ok(explorer_integration_status())
}

pub fn explorer_integration_status() -> ContextMenuStatus {
    if cfg!(target_os = "windows") {
        ContextMenuStatus {
            supported: true,
            installed: false,
            command_path: std::env::current_exe()
                .ok()
                .map(|path| path.to_string_lossy().to_string()),
            detail: "Windows context menu wiring is planned in the next phase.".to_string(),
        }
    } else {
        ContextMenuStatus {
            supported: false,
            installed: false,
            command_path: None,
            detail: "Windows integration is unavailable on this platform.".to_string(),
        }
    }
}
