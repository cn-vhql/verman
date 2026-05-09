<script lang="ts">
  import { onMount } from "svelte";
  import * as cmd from "../commands";
  import type { LogEntry } from "../types";

  let { onclose }: { onclose: () => void } = $props();

  let logs = $state<LogEntry[]>([]);
  let loading = $state(true);
  let errorMsg = $state("");

  onMount(async () => {
    try {
      logs = await cmd.getOperationLogs();
    } catch (e) {
      errorMsg = "加载日志失败";
    } finally {
      loading = false;
    }
  });

  async function handleClear() {
    if (!confirm("确定清除所有操作日志？")) return;
    try {
      await cmd.clearOperationLogs();
      logs = [];
    } catch (e) {
      errorMsg = "清除失败";
    }
  }
</script>

<div class="dialog-overlay" onclick={onclose}>
  <div class="dialog-panel" style="min-width: 640px; max-height: 70vh;" onclick={(e) => e.stopPropagation()}>
    <div class="dialog-title">操作日志</div>
    <div class="dialog-body" style="padding: 0;">
      {#if loading}
        <div class="loading">加载中...</div>
      {:else if errorMsg}
        <div class="error">{errorMsg}</div>
      {:else if logs.length === 0}
        <div class="empty">暂无操作日志</div>
      {:else}
        <div class="log-table">
          <div class="log-header">
            <span class="log-col-time">时间</span>
            <span class="log-col-level">级别</span>
            <span class="log-col-action">操作</span>
            <span class="log-col-details">详情</span>
          </div>
          <div class="log-body">
            {#each logs as log}
              <div class="log-row">
                <span class="log-col-time">{log.timestamp}</span>
                <span class="log-col-level log-level-{log.level}">{log.level}</span>
                <span class="log-col-action">{log.action}</span>
                <span class="log-col-details">{log.details}</span>
              </div>
            {/each}
          </div>
        </div>
      {/if}
    </div>
    <div class="dialog-footer">
      <button class="danger" onclick={handleClear} disabled={logs.length === 0}>清除日志</button>
      <span style="flex: 1"></span>
      <button onclick={onclose}>关闭</button>
    </div>
  </div>
</div>

<style>
  .log-table {
    display: flex;
    flex-direction: column;
    max-height: 55vh;
  }

  .log-header {
    display: flex;
    background: #f0f0f0;
    border-bottom: 1px solid var(--border);
    font-weight: 600;
    font-size: 12px;
    flex-shrink: 0;
  }

  .log-header span {
    padding: 6px 8px;
  }

  .log-body {
    flex: 1;
    overflow-y: auto;
  }

  .log-row {
    display: flex;
    font-size: 12px;
    border-bottom: 1px solid #f0f0f0;
  }

  .log-row:hover {
    background: #f5f5f5;
  }

  .log-row span {
    padding: 4px 8px;
  }

  .log-col-time { width: 160px; flex-shrink: 0; }
  .log-col-level { width: 50px; flex-shrink: 0; }
  .log-col-action { width: 100px; flex-shrink: 0; }
  .log-col-details { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

  .log-level-INFO { color: var(--primary); }
  .log-level-WARN { color: var(--warning); }
  .log-level-ERROR { color: var(--danger); }

  .loading, .error, .empty {
    text-align: center;
    padding: 32px;
    color: var(--text-secondary);
  }

  .error {
    color: var(--danger);
  }
</style>
