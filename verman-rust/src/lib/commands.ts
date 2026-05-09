import { invoke } from "@tauri-apps/api/core";
import type {
  AppConfig, CreateVersionResult, LogEntry, ProjectInfo,
  RollbackResult, ScanSnapshot, VersionDetails, VersionDiff, VersionInfo,
} from "./types";

// ── Project ──

export async function createProject(path: string): Promise<boolean> {
  return invoke("create_project", { workspacePath: path });
}

export async function openProject(path: string): Promise<boolean> {
  return invoke("open_project", { workspacePath: path });
}

export async function closeProject(): Promise<void> {
  return invoke("close_project");
}

export async function isProjectOpen(): Promise<boolean> {
  return invoke("is_project_open");
}

export async function getProjectPath(): Promise<string | null> {
  return invoke("get_project_path");
}

export async function getProjectInfo(): Promise<ProjectInfo | null> {
  return invoke("get_project_info");
}

export async function isProjectWorkspace(path: string): Promise<boolean> {
  return invoke("is_project_workspace", { path });
}

// ── Versions ──

export async function refreshWorkspace(force: boolean): Promise<ScanSnapshot> {
  return invoke("refresh_workspace", { force });
}

export async function getAllVersions(): Promise<VersionInfo[]> {
  return invoke("get_all_versions");
}

export async function createVersion(
  description: string,
  snapshotJson: string
): Promise<CreateVersionResult> {
  return invoke("create_version", { description, snapshotJson });
}

export async function rollbackToVersion(
  versionId: number,
  backupCurrent: boolean
): Promise<RollbackResult> {
  return invoke("rollback_to_version", { versionId, backupCurrent });
}

export async function getVersionDetails(
  versionId: number
): Promise<VersionDetails | null> {
  return invoke("get_version_details", { versionId });
}

export async function compareVersions(
  versionId1: number,
  versionId2: number
): Promise<VersionDiff> {
  return invoke("compare_versions", { versionId1, versionId2 });
}

export async function exportVersion(
  versionId: number,
  exportPath: string
): Promise<boolean> {
  return invoke("export_version", { versionId, exportPath });
}

// ── Config ──

export async function getConfig(): Promise<AppConfig> {
  return invoke("get_config");
}

export async function setIgnorePatterns(patterns: string[]): Promise<void> {
  return invoke("set_ignore_patterns", { patterns });
}

export async function setAutoBackup(enabled: boolean): Promise<void> {
  return invoke("set_auto_backup", { enabled });
}

export async function getRecentProjects(): Promise<string[]> {
  return invoke("get_recent_projects");
}

export async function resetConfig(): Promise<void> {
  return invoke("reset_config");
}

// ── Logs ──

export async function getOperationLogs(): Promise<LogEntry[]> {
  return invoke("get_operation_logs");
}

export async function clearOperationLogs(): Promise<void> {
  return invoke("clear_operation_logs");
}

// ── Context Menu ──

export async function checkContextMenuStatus(): Promise<number> {
  return invoke("check_context_menu_status");
}

export async function installContextMenu(
  exePath: string
): Promise<boolean> {
  return invoke("install_context_menu", { exePath });
}

export async function uninstallContextMenu(): Promise<boolean> {
  return invoke("uninstall_context_menu");
}

// ── Misc ──

export async function openFileWithSystem(path: string): Promise<void> {
  return invoke("open_file_with_system", { path });
}

// ── Dialog helpers ──

import { open, save } from "@tauri-apps/plugin-dialog";

export async function pickDirectory(): Promise<string | null> {
  const selected = await open({ directory: true, multiple: false, title: "选择目录" });
  return selected as string | null;
}

export async function pickSaveDirectory(): Promise<string | null> {
  const selected = await open({ directory: true, multiple: false, title: "选择导出目录" });
  return selected as string | null;
}
