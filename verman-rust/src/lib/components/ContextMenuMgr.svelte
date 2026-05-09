<script lang="ts">
  import { onMount } from "svelte";
  import * as cmd from "../commands";

  let { onclose }: { onclose: () => void } = $props();

  let status = $state<number | null>(null);
  let statusText = $state("检查中...");
  let actionMsg = $state("");
  let isError = $state(false);

  onMount(async () => {
    try {
      status = await cmd.checkContextMenuStatus();
      statusText = status > 0 ? "已安装 (旧版)" : "未安装";
      if (status === 2) statusText = "已安装 (新版)";
    } catch (e) {
      statusText = "无法检查状态";
    }
  });

  async function handleInstall() {
    actionMsg = "";
    isError = false;
    try {
      const ok = await cmd.installContextMenu("");
      if (ok) {
        actionMsg = "右键菜单安装成功";
        status = 2;
        statusText = "已安装 (新版)";
      } else {
        actionMsg = "安装失败";
        isError = true;
      }
    } catch (e: any) {
      actionMsg = `错误: ${e}`;
      isError = true;
    }
  }

  async function handleUninstall() {
    if (!confirm("确定卸载右键菜单？")) return;
    actionMsg = "";
    isError = false;
    try {
      const ok = await cmd.uninstallContextMenu();
      if (ok) {
        actionMsg = "卸载成功";
        status = 0;
        statusText = "未安装";
      } else {
        actionMsg = "卸载失败";
        isError = true;
      }
    } catch (e: any) {
      actionMsg = `错误: ${e}`;
      isError = true;
    }
  }
</script>

<div class="dialog-overlay" onclick={onclose}>
  <div class="dialog-panel" style="min-width: 400px;" onclick={(e) => e.stopPropagation()}>
    <div class="dialog-title">右键菜单管理</div>
    <div class="dialog-body">
      <div class="status-section">
        <span class="status-label">当前状态:</span>
        <span class="status-value" class:installed={status !== null && status > 0}>
          {statusText}
        </span>
      </div>

      <div class="info-text">
        右键菜单允许你在文件资源管理器中右键点击文件或目录，快速打开 VerMan 进行操作。
      </div>

      {#if actionMsg}
        <div class="action-msg" class:error={isError}>
          {actionMsg}
        </div>
      {/if}
    </div>
    <div class="dialog-footer">
      <button
        class="primary"
        onclick={handleInstall}
        disabled={status !== null && status > 0}
      >
        安装
      </button>
      <button
        class="danger"
        onclick={handleUninstall}
        disabled={status === null || status === 0}
      >
        卸载
      </button>
      <span style="flex: 1"></span>
      <button onclick={onclose}>关闭</button>
    </div>
  </div>
</div>

<style>
  .status-section {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 16px;
    padding: 12px;
    background: #f9f9f9;
    border-radius: 4px;
  }

  .status-label {
    font-weight: 600;
    font-size: 13px;
  }

  .status-value {
    font-size: 13px;
    color: var(--text-secondary);
  }

  .status-value.installed {
    color: var(--success);
    font-weight: 600;
  }

  .info-text {
    font-size: 12px;
    color: var(--text-secondary);
    line-height: 1.5;
    margin-bottom: 12px;
    padding: 8px;
    background: #f0f7ff;
    border-radius: 4px;
    border-left: 3px solid var(--primary);
  }

  .action-msg {
    padding: 8px 12px;
    border-radius: 4px;
    background: #f0fdf4;
    color: var(--success);
    font-size: 12px;
    font-weight: 600;
    text-align: center;
  }

  .action-msg.error {
    background: #fef2f2;
    color: var(--danger);
  }
</style>
