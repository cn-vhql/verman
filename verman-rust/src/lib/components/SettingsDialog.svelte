<script lang="ts">
  import { onMount } from "svelte";
  import * as cmd from "../commands";
  import type { AppConfig } from "../types";

  let { onclose }: { onclose: () => void } = $props();

  let config = $state<AppConfig | null>(null);
  let ignoreText = $state("");
  let autoBackup = $state(false);
  let recentProjects = $state<string[]>([]);
  let saveMessage = $state("");

  onMount(async () => {
    try {
      const cfg = await cmd.getConfig();
      config = cfg;
      ignoreText = cfg.ignore_patterns.join("\n");
      autoBackup = cfg.auto_backup;
      recentProjects = cfg.recent_projects;
    } catch (e) {
      saveMessage = "加载设置失败";
    }
  });

  async function handleSave() {
    try {
      const patterns = ignoreText
        .split("\n")
        .map((s) => s.trim())
        .filter((s) => s.length > 0 && !s.startsWith("#"));
      await cmd.setIgnorePatterns(patterns);
      await cmd.setAutoBackup(autoBackup);
      saveMessage = "设置已保存";
      setTimeout(() => onclose(), 1000);
    } catch (e) {
      saveMessage = "保存失败";
    }
  }

  async function handleReset() {
    if (!confirm("确定恢复默认设置？")) return;
    await cmd.resetConfig();
    saveMessage = "已恢复默认设置";
    setTimeout(() => onclose(), 800);
  }
</script>

<div class="dialog-overlay" onclick={onclose}>
  <div class="dialog-panel" style="min-width: 500px;" onclick={(e) => e.stopPropagation()}>
    <div class="dialog-title">设置</div>
    <div class="dialog-body">
      {#if config}
        <div class="setting-group">
          <label class="setting-label">忽略模式（每行一条）</label>
          <textarea
            class="setting-textarea"
            bind:value={ignoreText}
            placeholder=".git&#10;__pycache__&#10;*.log&#10;node_modules/"
            rows="8"
          ></textarea>
        </div>

        <div class="setting-group">
          <label class="setting-checkbox">
            <input type="checkbox" bind:checked={autoBackup} />
            <span>回滚时自动备份当前状态</span>
          </label>
        </div>

        <div class="setting-group">
          <div class="setting-label">最近打开的项目</div>
          {#if recentProjects.length > 0}
            <ul class="recent-list">
              {#each recentProjects as proj}
                <li>{proj}</li>
              {/each}
            </ul>
          {:else}
            <div class="setting-hint">暂无最近项目</div>
          {/if}
        </div>
      {:else}
        <div class="loading">加载中...</div>
      {/if}

      {#if saveMessage}
        <div class="save-message">{saveMessage}</div>
      {/if}
    </div>
    <div class="dialog-footer">
      <button onclick={handleReset} class="danger">恢复默认</button>
      <span style="flex: 1"></span>
      <button onclick={onclose}>取消</button>
      <button class="primary" onclick={handleSave}>保存</button>
    </div>
  </div>
</div>

<style>
  .setting-group {
    margin-bottom: 16px;
  }

  .setting-label {
    display: block;
    font-weight: 600;
    font-size: 12px;
    color: var(--text-secondary);
    margin-bottom: 6px;
    text-transform: uppercase;
  }

  .setting-textarea {
    width: 100%;
    min-height: 140px;
    resize: vertical;
    font-family: var(--font-mono);
    font-size: 12px;
  }

  .setting-checkbox {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    font-size: 13px;
  }

  .setting-checkbox input[type="checkbox"] {
    width: 16px;
    height: 16px;
    cursor: pointer;
  }

  .setting-hint {
    font-size: 12px;
    color: var(--text-secondary);
    font-style: italic;
  }

  .recent-list {
    list-style: none;
    padding: 0;
    margin: 0;
    max-height: 100px;
    overflow-y: auto;
  }

  .recent-list li {
    padding: 3px 0;
    font-size: 12px;
    color: var(--text-secondary);
    border-bottom: 1px solid #f0f0f0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .save-message {
    text-align: center;
    padding: 8px;
    color: var(--success);
    font-weight: 600;
  }

  .loading {
    text-align: center;
    color: var(--text-secondary);
    padding: 24px;
  }
</style>
