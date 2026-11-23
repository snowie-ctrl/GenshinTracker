<script lang="ts">
	import { safeColor } from './kit';
	import type { Segment } from './types';

	let { lines }: { lines: Segment[][] } = $props();
</script>

<div class="kit-text">
	{#each lines as line, i (i)}
		<p>{#each line as s, j (j)}<span style={safeColor(s.color) ? `color: ${safeColor(s.color)}` : undefined} class:i={s.italic}>{s.text}</span>{/each}</p>
	{/each}
</div>

<style>
	.kit-text p { margin: 0 0 4px; min-height: 0.6em; font-size: 12.5px; line-height: 1.5; color: #d8d6e2; }
	.i { font-style: italic; }
</style>
