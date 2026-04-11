use crate::models::{
    ContextMenuStatus, ExportResult, LaunchContext, OpenExternalResult, VersionDetails,
    VersionDiffResult, VersionFilePreview, WorkspaceData,
};
use serde::Serialize;
use serde_wasm_bindgen::{from_value, to_value};
use wasm_bindgen::prelude::*;

#[wasm_bindgen(inline_js = r#"
export async function invoke(command, payload) {
  if (window.__TAURI__?.core?.invoke) {
    return await window.__TAURI__.core.invoke(command, payload ?? {});
  }
  return null;
}

export function hasTauri() {
  return !!window.__TAURI__?.core?.invoke;
}

export function getPreferredLanguage() {
  try {
    return window.localStorage?.getItem("verman.language") || "zh";
  } catch (_) {
    return "zh";
  }
}

export function setPreferredLanguage(language) {
  try {
    window.localStorage?.setItem("verman.language", language);
  } catch (_) {}
}
"#)]
extern "C" {
    #[wasm_bindgen(catch, js_name = invoke)]
    async fn tauri_invoke(command: &str, payload: JsValue) -> Result<JsValue, JsValue>;

    #[wasm_bindgen(js_name = hasTauri)]
    fn has_tauri_runtime() -> bool;

    #[wasm_bindgen(js_name = getPreferredLanguage)]
    fn get_preferred_language_js() -> String;

    #[wasm_bindgen(js_name = setPreferredLanguage)]
    fn set_preferred_language_js(language: &str);
}

pub fn is_mock_mode() -> bool {
    !has_tauri_runtime()
}

pub fn get_preferred_language() -> String {
    let value = get_preferred_language_js();
    if value == "en" {
        "en".to_string()
    } else {
        "zh".to_string()
    }
}

#[allow(dead_code)]
pub fn set_preferred_language(language: &str) {
    let value = if language == "en" { "en" } else { "zh" };
    set_preferred_language_js(value);
}

async fn invoke_command<TInput, TOutput>(command: &str, payload: TInput) -> Result<TOutput, String>
where
    TInput: Serialize,
    TOutput: for<'de> serde::Deserialize<'de>,
{
    let payload = to_value(&payload).map_err(|error| error.to_string())?;
    let value = tauri_invoke(command, payload)
        .await
        .map_err(js_error_message)?;
    from_value(value).map_err(|error| error.to_string())
}

fn js_error_message(error: JsValue) -> String {
    if let Some(message) = error.as_string() {
        return message;
    }

    js_sys::JSON::stringify(&error)
        .ok()
        .and_then(|value| value.as_string())
        .unwrap_or_else(|| "Unknown error".to_string())
}

#[derive(Serialize)]
struct EmptyPayload {}

#[derive(Serialize)]
struct PathPayload<'a> {
    path: &'a str,
}

#[derive(Serialize)]
struct CreateVersionPayload<'a> {
    path: &'a str,
    description: &'a str,
}

#[derive(Serialize)]
struct RollbackPayload<'a> {
    path: &'a str,
    version_id: i64,
    backup_current: bool,
}

#[derive(Serialize)]
struct ComparePayload<'a> {
    path: &'a str,
    left_version_id: i64,
    right_version_id: i64,
}

#[derive(Serialize)]
struct ExportPayload<'a> {
    path: &'a str,
    version_id: i64,
    target_path: &'a str,
}

#[derive(Serialize)]
struct SaveIgnorePayload<'a> {
    path: &'a str,
    contents: &'a str,
}

#[derive(Serialize)]
struct VersionDetailsPayload<'a> {
    path: &'a str,
    version_id: i64,
}

#[derive(Serialize)]
struct VersionFilePayload<'a> {
    path: &'a str,
    version_id: i64,
    relative_path: &'a str,
}

pub async fn get_launch_context() -> Result<LaunchContext, String> {
    if is_mock_mode() {
        return Ok(LaunchContext { startup_path: None });
    }

    invoke_command("get_launch_context", EmptyPayload {}).await
}

pub async fn pick_workspace() -> Result<Option<String>, String> {
    if is_mock_mode() {
        return Ok(Some("H:/pythonwork/verman".to_string()));
    }

    invoke_command("pick_workspace", EmptyPayload {}).await
}

pub async fn pick_export_directory() -> Result<Option<String>, String> {
    if is_mock_mode() {
        return Ok(Some("H:/pythonwork/verman/export-demo".to_string()));
    }

    invoke_command("pick_export_directory", EmptyPayload {}).await
}

pub async fn open_workspace(path: &str) -> Result<WorkspaceData, String> {
    if is_mock_mode() {
        return Ok(mock_workspace(path));
    }

    invoke_command("open_workspace", PathPayload { path }).await
}

pub async fn refresh_workspace(path: &str) -> Result<WorkspaceData, String> {
    if is_mock_mode() {
        return Ok(mock_workspace(path));
    }

    invoke_command("refresh_workspace", PathPayload { path }).await
}

pub async fn create_version(path: &str, description: &str) -> Result<WorkspaceData, String> {
    if is_mock_mode() {
        let mut data = mock_workspace(path);
        data.versions.insert(
            0,
            crate::models::VersionEntry {
                id: 5,
                version_number: "v0005".to_string(),
                created_at: "2026-04-11 16:08:00".to_string(),
                description: description.to_string(),
                change_count: data.changes.len(),
            },
        );
        data.total_versions = data.versions.len();
        data.changed_files = 0;
        data.changes.clear();
        return Ok(data);
    }

    invoke_command("create_version", CreateVersionPayload { path, description }).await
}

pub async fn rollback_version(
    path: &str,
    version_id: i64,
    backup_current: bool,
) -> Result<WorkspaceData, String> {
    if is_mock_mode() {
        let mut data = mock_workspace(path);
        data.changed_files = 0;
        data.changes.clear();
        if let Some(version) = data
            .versions
            .iter()
            .find(|version| version.id == version_id)
        {
            data.workspace_path = format!("{} (rolled back to {})", path, version.version_number);
        }
        let _ = backup_current;
        return Ok(data);
    }

    invoke_command(
        "rollback_version",
        RollbackPayload {
            path,
            version_id,
            backup_current,
        },
    )
    .await
}

pub async fn compare_versions(
    path: &str,
    left_version_id: i64,
    right_version_id: i64,
) -> Result<VersionDiffResult, String> {
    if is_mock_mode() {
        let _ = path;
        return Ok(mock_diff(left_version_id, right_version_id));
    }

    invoke_command(
        "compare_versions",
        ComparePayload {
            path,
            left_version_id,
            right_version_id,
        },
    )
    .await
}

pub async fn get_version_details(path: &str, version_id: i64) -> Result<VersionDetails, String> {
    if is_mock_mode() {
        return Ok(mock_version_details(version_id));
    }

    invoke_command(
        "get_version_details",
        VersionDetailsPayload { path, version_id },
    )
    .await
}

pub async fn get_version_file_preview(
    path: &str,
    version_id: i64,
    relative_path: &str,
) -> Result<VersionFilePreview, String> {
    if is_mock_mode() {
        return Ok(mock_file_preview(version_id, relative_path));
    }

    invoke_command(
        "get_version_file_preview",
        VersionFilePayload {
            path,
            version_id,
            relative_path,
        },
    )
    .await
}

pub async fn open_version_file_external(
    path: &str,
    version_id: i64,
    relative_path: &str,
) -> Result<OpenExternalResult, String> {
    if is_mock_mode() {
        return Ok(OpenExternalResult {
            temp_path: format!("H:/temp/{}", relative_path),
        });
    }

    invoke_command(
        "open_version_file_external",
        VersionFilePayload {
            path,
            version_id,
            relative_path,
        },
    )
    .await
}

pub async fn export_version(
    path: &str,
    version_id: i64,
    target_path: &str,
) -> Result<ExportResult, String> {
    if is_mock_mode() {
        let _ = (path, version_id);
        return Ok(ExportResult {
            target_path: target_path.to_string(),
            file_count: 12,
        });
    }

    invoke_command(
        "export_version",
        ExportPayload {
            path,
            version_id,
            target_path,
        },
    )
    .await
}

pub async fn save_ignore_rules(path: &str, contents: &str) -> Result<WorkspaceData, String> {
    if is_mock_mode() {
        let mut data = mock_workspace(path);
        data.ignore_rules = contents.to_string();
        return Ok(data);
    }

    invoke_command("save_ignore_rules", SaveIgnorePayload { path, contents }).await
}

pub async fn get_context_menu_status() -> Result<ContextMenuStatus, String> {
    if is_mock_mode() {
        return Ok(ContextMenuStatus {
            supported: true,
            installed: false,
            command_path: Some("mock://verman-rust".to_string()),
            detail: "Browser preview is using mock context menu data.".to_string(),
        });
    }

    invoke_command("get_context_menu_status", EmptyPayload {}).await
}

pub async fn install_context_menu() -> Result<ContextMenuStatus, String> {
    if is_mock_mode() {
        return Ok(ContextMenuStatus {
            supported: true,
            installed: true,
            command_path: Some("mock://verman-rust".to_string()),
            detail: "Mock mode marked the context menu as installed.".to_string(),
        });
    }

    invoke_command("install_context_menu", EmptyPayload {}).await
}

pub async fn uninstall_context_menu() -> Result<ContextMenuStatus, String> {
    if is_mock_mode() {
        return Ok(ContextMenuStatus {
            supported: true,
            installed: false,
            command_path: Some("mock://verman-rust".to_string()),
            detail: "Mock mode marked the context menu as removed.".to_string(),
        });
    }

    invoke_command("uninstall_context_menu", EmptyPayload {}).await
}

fn mock_workspace(path: &str) -> WorkspaceData {
    WorkspaceData {
        workspace_path: path.to_string(),
        total_files: 38,
        total_versions: 4,
        changed_files: 5,
        ignore_rules: "# VerMan ignore rules\n*.log\n*.tmp\nnode_modules/\ndist/\n".to_string(),
        changes: vec![
            crate::models::ChangeEntry {
                relative_path: "src-tauri/src/main.rs".to_string(),
                status: "modify".to_string(),
                hash: "c1b2d339a122".to_string(),
                size: 8_432,
            },
            crate::models::ChangeEntry {
                relative_path: "src/app.rs".to_string(),
                status: "modify".to_string(),
                hash: "f0a9bc82e512".to_string(),
                size: 15_220,
            },
            crate::models::ChangeEntry {
                relative_path: "src-tauri/src/platform.rs".to_string(),
                status: "add".to_string(),
                hash: "8982ff1288ce".to_string(),
                size: 3_204,
            },
            crate::models::ChangeEntry {
                relative_path: "assets/style.css".to_string(),
                status: "modify".to_string(),
                hash: "8fa421aa119e".to_string(),
                size: 12_105,
            },
            crate::models::ChangeEntry {
                relative_path: "dist/old-preview.js".to_string(),
                status: "delete".to_string(),
                hash: "deadcafe0099".to_string(),
                size: 2_304,
            },
        ],
        versions: vec![
            crate::models::VersionEntry {
                id: 4,
                version_number: "v0004".to_string(),
                created_at: "2026-04-11 15:18:00".to_string(),
                description: "Added browser mock mode and export flow".to_string(),
                change_count: 7,
            },
            crate::models::VersionEntry {
                id: 3,
                version_number: "v0003".to_string(),
                created_at: "2026-04-11 14:32:00".to_string(),
                description: "Refined dashboard layout and release pipeline".to_string(),
                change_count: 9,
            },
            crate::models::VersionEntry {
                id: 2,
                version_number: "v0002".to_string(),
                created_at: "2026-04-11 13:47:00".to_string(),
                description: "Implemented Rust snapshot storage and rollback".to_string(),
                change_count: 11,
            },
            crate::models::VersionEntry {
                id: 1,
                version_number: "v0001".to_string(),
                created_at: "2026-04-11 13:12:00".to_string(),
                description: "Initial Tauri and Leptos scaffold".to_string(),
                change_count: 18,
            },
        ],
    }
}

fn mock_diff(left_version_id: i64, right_version_id: i64) -> VersionDiffResult {
    VersionDiffResult {
        left_version_id,
        right_version_id,
        left_version_label: format!("v{:04}", left_version_id),
        right_version_label: format!("v{:04}", right_version_id),
        added: 2,
        modified: 3,
        deleted: 1,
        entries: vec![
            crate::models::VersionDiffEntry {
                relative_path: "src-tauri/src/platform.rs".to_string(),
                status: "add".to_string(),
                left_hash: None,
                right_hash: Some("41aa7722ff18".to_string()),
                left_size: None,
                right_size: Some(3204),
            },
            crate::models::VersionDiffEntry {
                relative_path: "src/app.rs".to_string(),
                status: "modify".to_string(),
                left_hash: Some("90cc12f10218".to_string()),
                right_hash: Some("fa2122f10218".to_string()),
                left_size: Some(10_100),
                right_size: Some(15_220),
            },
            crate::models::VersionDiffEntry {
                relative_path: "dist/old-preview.js".to_string(),
                status: "delete".to_string(),
                left_hash: Some("778899aa1122".to_string()),
                right_hash: None,
                left_size: Some(2_304),
                right_size: None,
            },
        ],
    }
}

fn mock_version_details(version_id: i64) -> VersionDetails {
    VersionDetails {
        version: crate::models::VersionEntry {
            id: version_id,
            version_number: format!("v{:04}", version_id),
            created_at: "2026-04-11 15:18:00".to_string(),
            description: "补齐历史详情与预览能力".to_string(),
            change_count: 4,
        },
        previous_version_label: Some(format!("v{:04}", version_id.saturating_sub(1))),
        stats: crate::models::VersionStats {
            add_count: 1,
            modify_count: 2,
            delete_count: 1,
        },
        files: vec![
            crate::models::VersionChangeEntry {
                relative_path: "src/app.rs".to_string(),
                status: "modify".to_string(),
                hash: Some("fa2122f10218".to_string()),
                size: 15220,
                is_text: true,
            },
            crate::models::VersionChangeEntry {
                relative_path: "assets/style.css".to_string(),
                status: "modify".to_string(),
                hash: Some("8fa421aa119e".to_string()),
                size: 12105,
                is_text: true,
            },
            crate::models::VersionChangeEntry {
                relative_path: "assets/banner.png".to_string(),
                status: "add".to_string(),
                hash: Some("0011ffaa8822".to_string()),
                size: 483201,
                is_text: false,
            },
            crate::models::VersionChangeEntry {
                relative_path: "dist/old-preview.js".to_string(),
                status: "delete".to_string(),
                hash: None,
                size: 2304,
                is_text: true,
            },
        ],
    }
}

fn mock_file_preview(version_id: i64, relative_path: &str) -> VersionFilePreview {
    let previous = format!("v{:04}", version_id.saturating_sub(1));
    let current = format!("v{:04}", version_id);
    match relative_path {
        "assets/banner.png" => VersionFilePreview {
            relative_path: relative_path.to_string(),
            status: "add".to_string(),
            left_label: previous,
            right_label: current,
            left_text: None,
            right_text: None,
            is_text: false,
            can_open_external: true,
            note: Some("这是二进制资源文件，请使用系统默认软件打开历史版本。".to_string()),
        },
        "dist/old-preview.js" => VersionFilePreview {
            relative_path: relative_path.to_string(),
            status: "delete".to_string(),
            left_label: previous,
            right_label: current,
            left_text: Some("console.log('legacy build');\n".to_string()),
            right_text: None,
            is_text: true,
            can_open_external: true,
            note: Some("该文件在当前版本中被删除。".to_string()),
        },
        _ => VersionFilePreview {
            relative_path: relative_path.to_string(),
            status: "modify".to_string(),
            left_label: previous,
            right_label: current,
            left_text: Some(
                "fn panel_title() -> &'static str {\n    \"旧版界面\"\n}\n".to_string(),
            ),
            right_text: Some(
                "fn panel_title() -> &'static str {\n    \"Rust 版中文界面\"\n}\n".to_string(),
            ),
            is_text: true,
            can_open_external: true,
            note: Some("左右两侧分别是上一版本与当前版本的文本内容。".to_string()),
        },
    }
}
