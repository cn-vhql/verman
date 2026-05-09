export interface FileState {
  relative_path: string;
  file_hash: string;
  file_size: number;
  mtime_ns: number;
}

export interface BlockedFile {
  relative_path: string;
  file_size: number;
  reason: string;
}

export interface ChangeEntry {
  relative_path: string;
  file_hash: string;
  file_status: string;
}

export interface ScanSnapshot {
  current_files: Record<string, FileState>;
  changes: ChangeEntry[];
  blocked_files: BlockedFile[];
  scan_id: number;
}

export interface CreateVersionResult {
  success: boolean;
  version_number?: string;
  change_count: number;
  blocked_files: BlockedFile[];
  warnings: string[];
  error?: string;
}

export interface RollbackResult {
  success: boolean;
  restored_count: number;
  removed_count: number;
  warnings: string[];
  error?: string;
}

export interface VersionInfo {
  id: number;
  version_number: string;
  create_time: string;
  description?: string;
  change_count: number;
}

export interface VersionFileInfo {
  relative_path: string;
  file_hash: string;
  file_status: string;
  file_content?: number[];
}

export interface VersionStatistics {
  add_count: number;
  modify_count: number;
  delete_count: number;
  unmodified_count: number;
  total_count: number;
}

export interface VersionDetails {
  id: number;
  version_number: string;
  create_time: string;
  description?: string;
  change_count: number;
  files: VersionFileInfo[];
  statistics: VersionStatistics;
}

export interface DiffFileEntry {
  relative_path: string;
  file_hash: string;
  file_status: string;
}

export interface DiffSide {
  file_hash: string;
  file_status: string;
}

export interface DiffEntry {
  relative_path: string;
  file_in_v1: DiffSide;
  file_in_v2: DiffSide;
}

export interface VersionDiff {
  only_in_first?: DiffFileEntry[];
  only_in_second?: DiffFileEntry[];
  different?: DiffEntry[];
}

export interface ProjectInfo {
  project_path: string;
  create_time: string;
  version_count: number;
  latest_version: string;
  latest_time: string;
}

export interface AppConfig {
  recent_projects: string[];
  window_geometry: string;
  ignore_patterns: string[];
  auto_backup: boolean;
}

export interface LogEntry {
  timestamp: string;
  level: string;
  action: string;
  details: string;
  project_path: string;
}

export interface ProgressPayload {
  stage: string;
  current: number;
  total: number;
  message: string;
}

export type FileStatus = "add" | "modify" | "delete" | "unmodified";

export const STATUS_LABELS: Record<string, string> = {
  add: "新增",
  modify: "修改",
  delete: "删除",
  unmodified: "未变更",
};
