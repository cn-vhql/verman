use crate::models::ContextMenuStatus;
use anyhow::{anyhow, Result};
use std::env;
use std::process::Command;

const DIRECTORY_KEY: &str = r"HKCU\Software\Classes\Directory\shell\VerManRust";
const DIRECTORY_BACKGROUND_KEY: &str =
    r"HKCU\Software\Classes\Directory\Background\shell\VerManRust";

pub fn get_context_menu_status() -> ContextMenuStatus {
    #[cfg(target_os = "windows")]
    {
        let command_path = env::current_exe()
            .ok()
            .map(|path| path.to_string_lossy().to_string());

        let installed =
            reg_query(DIRECTORY_KEY).is_ok() && reg_query(DIRECTORY_BACKGROUND_KEY).is_ok();
        ContextMenuStatus {
            supported: true,
            installed,
            command_path,
            detail: if installed {
                "Right-click integration is enabled for folders and folder backgrounds.".to_string()
            } else {
                "Right-click integration is not installed yet.".to_string()
            },
        }
    }

    #[cfg(not(target_os = "windows"))]
    {
        ContextMenuStatus {
            supported: false,
            installed: false,
            command_path: None,
            detail: "Right-click integration is only available on Windows.".to_string(),
        }
    }
}

pub fn install_context_menu() -> Result<ContextMenuStatus> {
    #[cfg(target_os = "windows")]
    {
        let exe = env::current_exe()?;
        let exe_string = exe.to_string_lossy().to_string();

        reg_add_default_value(DIRECTORY_KEY, "Open with VerMan Rust")?;
        reg_add_named_value(DIRECTORY_KEY, "Icon", &exe_string)?;
        reg_add_default_value(
            &format!(r"{DIRECTORY_KEY}\command"),
            &format!(r#""{}" "%1""#, exe_string),
        )?;

        reg_add_default_value(DIRECTORY_BACKGROUND_KEY, "Open with VerMan Rust")?;
        reg_add_named_value(DIRECTORY_BACKGROUND_KEY, "Icon", &exe_string)?;
        reg_add_default_value(
            &format!(r"{DIRECTORY_BACKGROUND_KEY}\command"),
            &format!(r#""{}" "%V""#, exe_string),
        )?;

        return Ok(get_context_menu_status());
    }

    #[cfg(not(target_os = "windows"))]
    {
        Err(anyhow!(
            "Right-click integration is only available on Windows"
        ))
    }
}

pub fn uninstall_context_menu() -> Result<ContextMenuStatus> {
    #[cfg(target_os = "windows")]
    {
        let _ = reg_delete(DIRECTORY_KEY);
        let _ = reg_delete(DIRECTORY_BACKGROUND_KEY);
        return Ok(get_context_menu_status());
    }

    #[cfg(not(target_os = "windows"))]
    {
        Err(anyhow!(
            "Right-click integration is only available on Windows"
        ))
    }
}

#[cfg(target_os = "windows")]
fn reg_add_default_value(key: &str, value: &str) -> Result<()> {
    let output = Command::new("reg")
        .args(["add", key, "/ve", "/d", value, "/f"])
        .output()?;

    if output.status.success() {
        Ok(())
    } else {
        Err(anyhow!(String::from_utf8_lossy(&output.stderr).to_string()))
    }
}

#[cfg(target_os = "windows")]
fn reg_add_named_value(key: &str, name: &str, value: &str) -> Result<()> {
    let output = Command::new("reg")
        .args(["add", key, "/v", name, "/d", value, "/f"])
        .output()?;

    if output.status.success() {
        Ok(())
    } else {
        Err(anyhow!(String::from_utf8_lossy(&output.stderr).to_string()))
    }
}

#[cfg(target_os = "windows")]
fn reg_query(key: &str) -> Result<()> {
    let output = Command::new("reg").args(["query", key]).output()?;
    if output.status.success() {
        Ok(())
    } else {
        Err(anyhow!(String::from_utf8_lossy(&output.stderr).to_string()))
    }
}

#[cfg(target_os = "windows")]
fn reg_delete(key: &str) -> Result<()> {
    let output = Command::new("reg").args(["delete", key, "/f"]).output()?;
    if output.status.success() {
        Ok(())
    } else {
        Err(anyhow!(String::from_utf8_lossy(&output.stderr).to_string()))
    }
}
