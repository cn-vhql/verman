<script lang="ts">
  let { statusMessage, projectOpen }: { statusMessage: string; projectOpen: boolean } = $props();
</script>

<div class="status-bar">
  <span class="status-msg">{statusMessage}</span>
  <span class="status-right">
    {#if projectOpen}
      <span class="status-indicator"></span>
      项目已打开
    {:else}
      <span class="status-indicator closed"></span>
      未打开项目
    {/if}
  </span>
</div>

<style>
  .status-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 2px 12px;
    background: var(--surface);
    border-top: 1px solid var(--border);
    font-size: 12px;
    color: var(--text-secondary);
    flex-shrink: 0;
    min-height: 24px;
  }

  .status-msg {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .status-right {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
  }

  .status-indicator {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--success);
  }

  .status-indicator.closed {
    background: var(--text-secondary);
  }
</style>
