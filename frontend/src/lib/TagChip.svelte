<script lang="ts">
	import { TAG_HEX } from './teams';
	import type { Tag } from './types';

	let { tag, on = true, onclick }: { tag: Tag; on?: boolean; onclick?: () => void } = $props();
	const color = $derived(TAG_HEX[tag.color] ?? '#888');
</script>

{#if onclick}
	<button type="button" class="tag" class:off={!on} style="--c: {color}" {onclick} aria-pressed={on}>
		{#if tag.builtin}<span aria-hidden="true">🔒</span>{/if}{tag.name}
	</button>
{:else}
	<span class="tag" style="--c: {color}">{tag.name}</span>
{/if}

<style>
	.tag { display: inline-flex; gap: 3px; align-items: center; border: 1px solid var(--c); color: var(--text);
		background: color-mix(in srgb, var(--c) 30%, transparent); border-radius: 10px; padding: 1px 8px;
		font-size: 12px; line-height: 18px; }
	button.tag { cursor: pointer; }
	.off { background: transparent; opacity: 0.7; }
</style>
