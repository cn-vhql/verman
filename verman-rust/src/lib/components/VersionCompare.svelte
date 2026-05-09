<script lang="ts">
  import { onMount } from "svelte";
  import * as cmd from "../commands";
  import type { VersionInfo, VersionDiff, DiffFileEntry, DiffEntry } from "../types";
  import { STATUS_LABELS } from "../types";

  let { versions, onclose }: { versions: VersionInfo[]; onclose: () => void } = $props();

  let v1 = $state<number>(versions.length >= 2 ? versions[versions.length - 2].id : 0);
  let v2 = $state<number>(versions.length >= 1 ? versions[versions.length - 1].id : 0);
  let diff = $state<VersionDiff | null>(null);
  let loading = $state(false);
  let errorMsg = $state("");

  async function handleCompare() {
    if (v1 === v2) {
      errorMsg = "请选择两个不同的版本";
      return;
    }
    loading = true;
    errorMsg = "";
    diff = null;
    try {
      diff = await cmd.compareVersions(v1, v2);
    } catch (e: any) {
      errorMsg = `比较失败: ${e}`;
    } finally {
      loading = false;
    }
  }

  function totalChanges(): number {
    if (!diff) return 0;
    const only1 = diff.only_in_first?.length ?? 0;
    const only2 = diff.only_in_second?.length ?? 0;
    const diffs = diff.different?.length ?? 0;
    return only1 + only2 + diffs;
  }

  function fileStatusIcon(entry: DiffFileEntry): string {
    return STATUS_LABELS[entry.file_status] ?? entry.file_status;
  }

  function diffStatus(e: DiffEntry): string {
    if (e.file_in_v1.file_status === "delete") return "删除";
    if (e.file_in_v2.file_status === "add") return "新增";
    return "修改";
  }
</script>

<div class="dialog-overlay" onclick={onclose}>
  <div class="dialog-panel" style="min-width: 600px; min-height: 400px;" onclick={(e) => e.stopPropagation()}>
    <div class="dialog-title">版本比较</div>
    <div class="dialog-body">
      <div class="compare-controls">
        <select bind:value={v1}>
          {#each versions as v}
            <option value={v.id}>v{v.version_number} ({v.create_time})</option>
          {/each}
        </select>
        <span class="vs">vs</span>
        <select bind:value={v2}>
          {#each versions as v}
            <option value={v.id}>v{v.version_number} ({v.create_time})</option>
          {/each}
        </select>
        <button class="primary" onclick={handleCompare} disabled={loading}>
          {loading ? "比较中..." : "比较"}
        </button>
      </div>

      {#if errorMsg}
        <div class="error-msg">{errorMsg}</div>
      {/if}

      {#if diff}
        <div class="diff-stats">
          差异总数: {totalChanges()}
        </div>
        <div class="diff-results">
          {#if diff.only_in_first && diff.only_in_first.length > 0}
            <div class="diff-section">
              <div class="diff-section-title">仅在第一版本中</div>
              {#each diff.only_in_first as entry}
                <div class="diff-row">
                  <span class="diff-status">{fileStatusIcon(entry)}</span>
                  <span class="diff-path">{entry.relative_path}</span>
                </div>
              {/each}
            </div>
          {/if}

          {#if diff.only_in_second && diff.only_in_second.length > 0}
            <div class="diff-section">
              <div class="diff-section-title">仅在第二版本中</div>
              {#each diff.only_in_second as entry}
                <div class="diff-row">
                  <span class="diff-status">{fileStatusIcon(entry)}</span>
                  <span class="diff-path">{entry.relative_path}</span>
                </div>
              {/each}
            </div>
          {/if}

          {#if diff.different && diff.different.length > 0}
            <div class="diff-section">
              <div class="diff-section-title">内容不同</div>
              {#each diff.different as entry}
                <div class="diff-row">
                  <span class="diff-status">{diffStatus(entry)}</span>
                  <span class="diff-path">{entry.relative_path}</span>
                </div>
              {/each}
            </div>
          {/if}

          {#if totalChanges() === 0}
            <div class="no-diff">两个版本完全一致</div>
          {/if}
        </div>
      {:else if !loading}
        <div class="no-diff">选择两个版本后点击"比较"</div>
      {/if}
    </div>
    <div class="dialog-footer">
      <button onclick={onclose}>关闭</button>
    </div>
  </div>
</div>

<style>
  .compare-controls {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 16px;
    flex-wrap: wrap;
  }

  .compare-controls select {
    flex: 1;
    min-width: 0;
  }

  .vs {
    font-weight: 600;
    color: var(--text-secondary);
    flex-shrink: 0;
  }

  .error-msg {
    color: var(--danger);
    padding: 8px;
    margin-bottom: 8px;
    background: #fef2f2;
    border-radius: 4px;
    font-size: 12px;
  }

  .diff-stats {
    font-weight: 600;
    font-size: 13px;
    margin-bottom: 8px;
    padding: 8px;
    background: #f0f0f0;
    border-radius: 4px;
  }

  .diff-results {
    max-height: 40vh;
    overflow-y: auto;
    border: 1px solid var(--border);
    border-radius: 4px;
  }

  .diff-section {
    border-bottom: 1px solid var(--border);
  }

  .diff-section:last-child {
    border-bottom: none;
  }

  .diff-section-title {
    font-weight: 600;
    font-size: 12px;
    padding: 6px 8px;
    background: #f5f5f5;
    border-bottom: 1px solid var(--border);
    text-transform: uppercase;
    color: var(--text-secondary);
  }

  .diff-row {
    display: flex;
    padding: 4px 8px;
    font-size: 12px;
    border-bottom: 1px solid #f0f0f0;
  }

  .diff-row:hover {
    background: #f5f5f5;
  }

  .diff-status {
    width: 40px;
    flex-shrink: 0;
    color: var(--primary);
  }

  .diff-path {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .no-diff {
    text-align: center;
    padding: 32px;
    color: var(--text-secondary);
  }
</style>
