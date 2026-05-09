<script lang="ts">
  import { onMount } from "svelte";
  import * as cmd from "../commands";
  import type { VersionDetails } from "../types";
  import { STATUS_LABELS } from "../types";
  import VirtualList from "./VirtualList.svelte";

  let { versionId, onclose }: { versionId: number; onclose: () => void } = $props();

  let details = $state<VersionDetails | null>(null);
  let loading = $state(true);
  let errorMsg = $state("");

  onMount(async () => {
    try {
      details = await cmd.getVersionDetails(versionId);
    } catch (e: any) {
      errorMsg = `加载版本详情失败: ${e}`;
    } finally {
      loading = false;
    }
  });

  async function handleOpenFile(path: string) {
    try {
      await cmd.openFileWithSystem(path);
    } catch (e) {
      // ignore
    }
  }
</script>

<div class="dialog-overlay" onclick={onclose}>
  <div class="dialog-panel" style="min-width: 560px; max-height: 75vh;" onclick={(e) => e.stopPropagation()}>
    <div class="dialog-title">版本详情</div>
    <div class="dialog-body">
      {#if loading}
        <div class="loading">加载中...</div>
      {:else if errorMsg}
        <div class="error-msg">{errorMsg}</div>
      {:else if details}
        <div class="detail-header">
          <div class="detail-row">
            <span class="detail-label">版本号:</span>
            <span class="detail-value">{details.version_number}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">创建时间:</span>
            <span class="detail-value">{details.create_time}</span>
          </div>
          {#if details.description}
            <div class="detail-row">
              <span class="detail-label">描述:</span>
              <span class="detail-value">{details.description}</span>
            </div>
          {/if}
          <div class="detail-row">
            <span class="detail-label">变更总数:</span>
            <span class="detail-value">{details.change_count}</span>
          </div>
        </div>

        {#if details.statistics}
          <div class="stats-row">
            <span class="stat stat-add">新增: {details.statistics.add_count}</span>
            <span class="stat stat-modify">修改: {details.statistics.modify_count}</span>
            <span class="stat stat-delete">删除: {details.statistics.delete_count}</span>
            <span class="stat stat-unmod">未变更: {details.statistics.unmodified_count}</span>
          </div>
        {/if}

        <div class="detail-files">
          <div class="files-header">
            <span class="file-col-status">状态</span>
            <span class="file-col-path">文件路径</span>
          </div>
          <div class="files-body">
            {#if details.files.length > 0}
              <VirtualList items={details.files} rowHeight={24} overscan={10}>
                {#snippet children(file)}
                  <div
                    class="file-row"
                    onclick={() => handleOpenFile(file.relative_path)}
                    title="在资源管理器中打开"
                  >
                    <span class="file-col-status status-{file.file_status}">
                      {STATUS_LABELS[file.file_status] ?? file.file_status}
                    </span>
                    <span class="file-col-path">{file.relative_path}</span>
                  </div>
                {/snippet}
              </VirtualList>
            {:else}
              <div class="tree-empty">无文件</div>
            {/if}
          </div>
        </div>
      {/if}
    </div>
    <div class="dialog-footer">
      <button onclick={onclose}>关闭</button>
    </div>
  </div>
</div>

<style>
  .detail-header {
    margin-bottom: 12px;
    padding: 8px;
    background: #f9f9f9;
    border-radius: 4px;
  }

  .detail-row {
    display: flex;
    padding: 3px 0;
    font-size: 13px;
  }

  .detail-label {
    width: 80px;
    flex-shrink: 0;
    color: var(--text-secondary);
    font-weight: 600;
  }

  .detail-value {
    flex: 1;
  }

  .loading, .error-msg {
    text-align: center;
    padding: 32px;
    color: var(--text-secondary);
  }

  .error-msg {
    color: var(--danger);
  }

  .stats-row {
    display: flex;
    gap: 12px;
    margin-bottom: 12px;
    padding: 8px;
    background: #f0f0f0;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 600;
    flex-wrap: wrap;
  }

  .stat-add { color: var(--success); }
  .stat-modify { color: var(--primary); }
  .stat-delete { color: var(--danger); }
  .stat-unmod { color: var(--text-secondary); }

  .detail-files {
    border: 1px solid var(--border);
    border-radius: 4px;
    display: flex;
    flex-direction: column;
    max-height: 35vh;
  }

  .files-header {
    display: flex;
    background: #f0f0f0;
    border-bottom: 1px solid var(--border);
    font-weight: 600;
    font-size: 12px;
    flex-shrink: 0;
  }

  .files-header span {
    padding: 4px 8px;
  }

  .files-body {
    flex: 1;
    overflow-y: auto;
  }

  .file-row {
    display: flex;
    font-size: 12px;
    border-bottom: 1px solid #f0f0f0;
    cursor: pointer;
  }

  .file-row:hover {
    background: #f5f5f5;
  }

  .file-row span {
    padding: 3px 8px;
  }

  .file-col-status { width: 50px; flex-shrink: 0; }
  .file-col-path { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

  .status-add { color: var(--success); }
  .status-modify { color: var(--primary); }
  .status-delete { color: var(--danger); }
</style>
