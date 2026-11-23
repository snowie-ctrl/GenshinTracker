<script lang="ts">
	import { imgSrc } from './img';
	import type { Kit } from './types';

	let { kit, owned, target = null }: { kit: Kit | null; owned: number; target?: number | null } = $props();
	const items = $derived(
		[1, 2, 3, 4, 5, 6].map((n) => ({ n, icon: kit?.constellations.find((c) => c.index === n)?.icon ?? null }))
	);
</script>

<div class="row">
	{#each items as it (it.n)}
		<div class="c" class:on={it.n <= owned} class:want={target !== null && it.n > owned && it.n <= target}
			title="C{it.n}">
			{#if imgSrc(it.icon)}<img src={imgSrc(it.icon)} alt="" />{:else}<span>{it.n}</span>{/if}
		</div>
	{/each}
</div>

<style>
	.row { display: flex; gap: 8px; flex-wrap: wrap; }
	.c { width: 40px; height: 40px; border-radius: 50%; background: rgba(255, 255, 255, 0.06);
		border: 1px solid var(--glass-border); display: flex; align-items: center; justify-content: center; color: var(--muted); }
	.c img { width: 32px; height: 32px; opacity: 0.25; filter: grayscale(1); }
	.c.on { border-color: var(--el, var(--gold)); }
	.c.on img { opacity: 1; filter: none; }
	.c.want { border: 1px dashed var(--el, var(--gold)); }
</style>
