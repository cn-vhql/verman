<script lang="ts">
  import { onMount } from "svelte";
  import * as cmd from "./lib/commands";
  import StatusBar from "./lib/components/StatusBar.svelte";
  import SettingsDialog from "./lib/components/SettingsDialog.svelte";
  import VersionCompare from "./lib/components/VersionCompare.svelte";
  import VersionDetails from "./lib/components/VersionDetails.svelte";
  import LogViewer from "./lib/components/LogViewer.svelte";
  import ContextMenuMgr from "./lib/components/ContextMenuMgr.svelte";
  import VirtualList from "./lib/components/VirtualList.svelte";
  import type {
    ScanSnapshot, ChangeEntry, VersionInfo, CreateVersionResult, RollbackResult,
    ProjectInfo, AppConfig, ProgressPayload,
  } from "./lib/types";
  import { STATUS_LABELS } from "./lib/types";
  import { listen } from "@tauri-apps/api/event";

  let projectOpen = $state(false);
  let projectPath = $state("");
  let projectInfo = $state<ProjectInfo | null>(null);
  let changes = $state<ChangeEntry[]>([]);
  let versions = $state<VersionInfo[]>([]);
  let statusMessage = $state("就绪");
  let isBusy = $state(false);
  let selectedVersionId = $state<number | null>(null);
  let snapshotJson = $state("");

  // Dialog visibility
  let showSettings = $state(false);
  let showCompare = $state(false);
  let showVersionDetails = $state(false);
  let showLogs = $state(false);
  let showContextMenu = $state(false);
  let showAbout = $state(false);
  let progress = $state<ProgressPayload | null>(null);

  onMount(() => {
    const unlisteners: Array<() => void> = [];
    const setupListeners = async () => {
      unlisteners.push(
        await listen<ProgressPayload>("verman:progress", (event) => {
          const p = event.payload;
          progress = p;
          if (p.stage === "done") {
            setTimeout(() => { progress = null; }, 2000);
          }
        })
      );
      unlisteners.push(
        await listen("verman:files-changed", () => {
          if (projectOpen) refreshData(false);
        })
      );
    };
    setupListeners();
    return () => {
      unlisteners.forEach((fn) => fn());
    };
  });

  async function refreshData(force = true) {
    if (!projectOpen) return;
    isBusy = true;
    statusMessage = "正在刷新工作区...";
    try {
      const snapshot: ScanSnapshot = await cmd.refreshWorkspace(force);
      changes = snapshot.changes;
      snapshotJson = JSON.stringify(snapshot);
      versions = await cmd.getAllVersions();
      projectInfo = await cmd.getProjectInfo();
      statusMessage = `变更文件: ${changes.length} | 版本数: ${versions.length}`;
    } catch (e: any) {
      statusMessage = "刷新失败";
      console.error(e);
    } finally {
      isBusy = false;
    }
  }

  async function handleNewProject() {
    const path = await cmd.pickDirectory();
    if (!path) return;
    isBusy = true;
    statusMessage = "正在创建项目...";
    try {
      const ok = await cmd.createProject(path);
      if (ok) {
        projectOpen = true;
        projectPath = path;
        await refreshData();
      } else {
        statusMessage = "项目创建失败";
      }
    } catch (e: any) {
      statusMessage = `错误: ${e}`;
    } finally {
      isBusy = false;
    }
  }

  async function handleOpenProject(path?: string) {
    if (!path) {
      path = await cmd.pickDirectory() ?? undefined;
    }
    if (!path) return;
    isBusy = true;
    statusMessage = "正在打开项目...";
    try {
      const ok = await cmd.openProject(path);
      if (ok) {
        projectOpen = true;
        projectPath = path;
        await refreshData();
      } else {
        statusMessage = "项目打开失败";
      }
    } catch (e: any) {
      statusMessage = `错误: ${e}`;
    } finally {
      isBusy = false;
    }
  }

  async function handleCloseProject() {
    await cmd.closeProject();
    projectOpen = false;
    projectPath = "";
    projectInfo = null;
    changes = [];
    versions = [];
    selectedVersionId = null;
    snapshotJson = "";
    statusMessage = "请先创建或打开项目";
  }

  async function handleCommit() {
    if (!snapshotJson || changes.length === 0) {
      statusMessage = "没有文件变更，无需提交";
      return;
    }
    const desc = prompt("请输入版本描述：");
    if (desc === null) return;
    const trimmed = desc.trim();
    if (!trimmed) {
      statusMessage = "版本描述不能为空";
      return;
    }
    isBusy = true;
    statusMessage = "正在提交版本...";
    try {
      const result: CreateVersionResult = await cmd.createVersion(trimmed, snapshotJson);
      if (result.success) {
        await refreshData();
      } else {
        statusMessage = result.error || "版本创建失败";
      }
    } catch (e: any) {
      statusMessage = `错误: ${e}`;
    } finally {
      isBusy = false;
    }
  }

  async function handleRollback() {
    if (selectedVersionId === null) return;
    if (!confirm("确定要回滚到选中的版本吗？")) return;
    const backup = confirm("是否备份当前状态？（取消=否）");
    isBusy = true;
    statusMessage = "正在回滚版本...";
    try {
      const result: RollbackResult = await cmd.rollbackToVersion(selectedVersionId, backup);
      if (result.success) {
        statusMessage = `回滚成功: 恢复${result.restored_count}个文件, 删除${result.removed_count}个文件`;
        await refreshData();
      } else {
        statusMessage = result.error || "回滚失败";
      }
    } catch (e: any) {
      statusMessage = `错误: ${e}`;
    } finally {
      isBusy = false;
    }
  }

  async function handleExport() {
    if (selectedVersionId === null) return;
    const exportPath = await cmd.pickSaveDirectory();
    if (!exportPath) return;
    isBusy = true;
    statusMessage = "正在导出版本...";
    try {
      const ok = await cmd.exportVersion(selectedVersionId, exportPath);
      statusMessage = ok ? "导出成功" : "导出失败";
    } catch (e: any) {
      statusMessage = `错误: ${e}`;
    } finally {
      isBusy = false;
    }
  }

  function handleShowDetails() {
    if (selectedVersionId !== null) {
      showVersionDetails = true;
    }
  }

  function handleShowCompare() {
    if (versions.length >= 2) {
      showCompare = true;
    }
  }
</script>

<div class="app-container">
  <!-- Menu Bar -->
  <div class="menu-bar">
    <div class="menu-group">
      <button onclick={handleNewProject} disabled={isBusy}>新建项目</button>
      <button onclick={() => handleOpenProject()} disabled={isBusy}>打开项目</button>
      <button onclick={handleCloseProject} disabled={!projectOpen || isBusy}>关闭项目</button>
      <span class="menu-sep"></span>
      <button onclick={handleCommit} disabled={!projectOpen || isBusy || changes.length === 0}>提交版本</button>
      <button onclick={handleRollback} disabled={!projectOpen || isBusy || selectedVersionId === null}>回滚版本</button>
      <button onclick={handleExport} disabled={!projectOpen || isBusy || selectedVersionId === null}>导出版本</button>
      <button onclick={handleShowCompare} disabled={versions.length < 2}>比较版本</button>
      <span class="menu-sep"></span>
      <button onclick={() => showSettings = true}>设置</button>
      <button onclick={() => showContextMenu = true}>右键菜单</button>
      <button onclick={() => showLogs = true}>操作日志</button>
      <button onclick={() => showAbout = true}>关于</button>
    </div>
  </div>

  <!-- Progress Bar -->
  {#if progress}
    <div class="progress-bar">
      <div class="progress-fill" style="width: {progress.total > 0 ? (progress.current / progress.total * 100) : 0}%"></div>
      <span class="progress-text">{progress.message}</span>
    </div>
  {/if}

  <!-- Main Content -->
  <div class="main-content">
    <!-- Left Panel: Project Info + Changes -->
    <div class="panel left-panel">
      <div class="panel-section">
        <div class="panel-title">项目信息</div>
        <div class="project-path">
          {projectOpen ? projectPath : "未打开项目"}
        </div>
      </div>
      <div class="panel-section" class:expanded={true}>
        <div class="panel-title">文件变更 ({changes.length})</div>
        <div class="tree-container">
          <div class="tree-header-row">
            <span class="col-status">状态</span>
            <span class="col-path">文件路径</span>
          </div>
          {#if changes.length > 0}
            <VirtualList items={changes} rowHeight={24} overscan={10}>
              {#snippet children(change)}
                <div class="tree-row">
                  <span class="col-status status-{change.file_status}">
                    {STATUS_LABELS[change.file_status] ?? change.file_status}
                  </span>
                  <span class="col-path">{change.relative_path}</span>
                </div>
              {/snippet}
            </VirtualList>
          {:else}
            <div class="tree-empty">无变更</div>
          {/if}
        </div>
      </div>
      <button class="refresh-btn" onclick={() => refreshData()} disabled={!projectOpen || isBusy}>
        刷新
      </button>
    </div>

    <!-- Right Panel: Version History -->
    <div class="panel right-panel">
      <div class="panel-section" class:expanded={true}>
        <div class="panel-title">版本历史 ({versions.length})</div>
        <div class="tree-container">
          <div class="tree-header-row">
            <span class="col-ver">版本号</span>
            <span class="col-time">创建时间</span>
            <span class="col-desc">描述</span>
            <span class="col-count">变更数</span>
          </div>
          <div class="tree-body">
            {#each versions as ver}
              <div
                class="tree-row version-row"
                class:selected={selectedVersionId === ver.id}
                onclick={() => selectedVersionId = ver.id}
                ondblclick={() => { selectedVersionId = ver.id; showVersionDetails = true; }}
              >
                <span class="col-ver">{ver.version_number}</span>
                <span class="col-time">{ver.create_time}</span>
                <span class="col-desc">{ver.description || "无描述"}</span>
                <span class="col-count">{ver.change_count}</span>
              </div>
            {:else}
              <div class="tree-empty">暂无版本</div>
            {/each}
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Status Bar -->
  <StatusBar {statusMessage} {projectOpen} />

  <!-- Dialogs -->
  {#if showSettings}
    <SettingsDialog onclose={() => showSettings = false} />
  {/if}

  {#if showCompare}
    <VersionCompare {versions} onclose={() => showCompare = false} />
  {/if}

  {#if showVersionDetails && selectedVersionId !== null}
    <VersionDetails
      versionId={selectedVersionId}
      onclose={() => showVersionDetails = false}
    />
  {/if}

  {#if showLogs}
    <LogViewer onclose={() => showLogs = false} />
  {/if}

  {#if showContextMenu}
    <ContextMenuMgr onclose={() => showContextMenu = false} />
  {/if}

  {#if showAbout}
    <div class="dialog-overlay" onclick={() => showAbout = false}>
      <div class="dialog-panel" style="min-width: 320px;" onclick={(e) => e.stopPropagation()}>
        <div class="dialog-title">关于 VerMan</div>
        <div class="dialog-body" style="text-align: center; padding: 24px;">
          <h2 style="margin-bottom: 8px;">VerMan</h2>
          <p style="color: var(--text-secondary); margin-bottom: 16px;">版本管理工具</p>
          <p style="color: var(--text-secondary); font-size: 12px;">
            Windows 优先的本地文件版本管理工具。
            <br>支持工作区扫描、版本快照、回滚、导出和版本比较。
            <br><br>版本: V1.0.2 (Rust/Tauri)
          </p>
        </div>
        <div class="dialog-footer">
          <button onclick={() => showAbout = false}>关闭</button>
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .app-container {
    display: flex;
    flex-direction: column;
    height: 100vh;
    overflow: hidden;
  }

  .menu-bar {
    display: flex;
    align-items: center;
    padding: 4px 8px;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    gap: 4px;
    flex-shrink: 0;
  }

  .menu-group {
    display: flex;
    align-items: center;
    gap: 4px;
    flex-wrap: wrap;
  }

  .menu-sep {
    width: 1px;
    height: 20px;
    background: var(--border);
    margin: 0 4px;
  }

  .main-content {
    display: flex;
    flex: 1;
    overflow: hidden;
    padding: 8px;
    gap: 8px;
  }

  .panel {
    display: flex;
    flex-direction: column;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow: hidden;
  }

  .left-panel {
    flex: 1;
    min-width: 0;
  }

  .right-panel {
    flex: 1;
    min-width: 0;
  }

  .panel-section {
    padding: 8px;
    display: flex;
    flex-direction: column;
  }

  .panel-section.expanded {
    flex: 1;
    overflow: hidden;
  }

  .panel-title {
    font-weight: 600;
    font-size: 12px;
    text-transform: uppercase;
    color: var(--text-secondary);
    padding-bottom: 4px;
    margin-bottom: 4px;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }

  .project-path {
    font-size: 12px;
    color: var(--text-secondary);
    word-break: break-all;
    padding: 4px 0;
  }

  .tree-container {
    display: flex;
    flex-direction: column;
    flex: 1;
    overflow: hidden;
    border: 1px solid var(--border);
    border-radius: 4px;
  }

  .tree-header-row {
    display: flex;
    background: #f0f0f0;
    border-bottom: 1px solid var(--border);
    font-weight: 600;
    font-size: 12px;
    flex-shrink: 0;
  }

  .tree-header-row span {
    padding: 4px 8px;
  }

  .tree-body {
    flex: 1;
    overflow-y: auto;
    min-height: 100px;
  }

  .tree-row {
    display: flex;
    border-bottom: 1px solid #f0f0f0;
    font-size: 12px;
  }

  .tree-row:hover {
    background: #f5f5f5;
  }

  .version-row {
    cursor: pointer;
  }

  .version-row.selected {
    background: #dbeafe;
  }

  .tree-empty {
    padding: 16px;
    text-align: center;
    color: var(--text-secondary);
    font-size: 12px;
  }

  .col-status { width: 60px; padding: 3px 8px; flex-shrink: 0; }
  .col-path { flex: 1; padding: 3px 8px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .col-ver { width: 80px; padding: 3px 8px; flex-shrink: 0; }
  .col-time { width: 140px; padding: 3px 8px; flex-shrink: 0; }
  .col-desc { flex: 1; padding: 3px 8px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .col-count { width: 60px; padding: 3px 8px; flex-shrink: 0; text-align: center; }

  .status-add { color: var(--success); }
  .status-modify { color: var(--primary); }
  .status-delete { color: var(--danger); }

  .refresh-btn {
    margin: 8px;
    flex-shrink: 0;
  }

  .progress-bar {
    position: relative;
    height: 24px;
    margin: 0 8px;
    background: var(--border);
    border-radius: 4px;
    overflow: hidden;
    flex-shrink: 0;
  }

  .progress-fill {
    height: 100%;
    background: var(--primary);
    transition: width 0.3s ease;
    border-radius: 4px;
  }

  .progress-text {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    color: var(--text-primary);
    text-shadow: 0 0 4px rgba(255,255,255,0.8);
  }
</style>
