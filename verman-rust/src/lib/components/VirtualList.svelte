<script lang="ts">
  import type { Snippet } from "svelte";

  let {
    items,
    children,
    rowHeight = 24,
    overscan = 10,
  }: {
    items: any[];
    children: Snippet<[any]>;
    rowHeight?: number;
    overscan?: number;
  } = $props();

  let containerEl: HTMLDivElement;
  let scrollTop = $state(0);
  let containerHeight = $state(0);

  let totalHeight = $derived(items.length * rowHeight);
  let startIndex = $derived(Math.max(0, Math.floor(scrollTop / rowHeight) - overscan));
  let endIndex = $derived(Math.min(items.length, Math.ceil((scrollTop + containerHeight) / rowHeight) + overscan));
  let visibleItems = $derived(items.slice(startIndex, endIndex));
  let paddingTop = $derived(startIndex * rowHeight);
  let paddingBottom = $derived(totalHeight - endIndex * rowHeight);
</script>

<div
  bind:this={containerEl}
  class="virtual-list"
  onscroll={() => scrollTop = containerEl.scrollTop}
  bind:clientHeight={containerHeight}
>
  <div style="padding-top: {paddingTop}px; padding-bottom: {paddingBottom}px;">
    {#each visibleItems as item, i (startIndex + i)}
      {@render children(item)}
    {/each}
  </div>
</div>

<style>
  .virtual-list {
    flex: 1;
    overflow-y: auto;
    min-height: 100px;
  }
</style>
