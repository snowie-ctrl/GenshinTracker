<script lang="ts">
	import { timeLeft } from '$lib/events';
	import { imgSrc } from '$lib/img';
	import type { Timer } from '$lib/types';
	let { timers, now }: { timers: Timer[]; now: number } = $props();
</script>

<section class="panel" data-testid="timers">
	<h2>Timers</h2>
	{#if timers.length === 0}
		<p class="muted">Sync to load timers</p>
	{:else}
		<ul>
			{#each timers as t, i (i)}
				{@const ready = Date.parse(t.ready_at) <= now}
				<li>{#if imgSrc(t.icon)}<img src={imgSrc(t.icon)} alt="" />{/if}<span class="label">{t.label}</span>
					<span class:ready>{ready ? 'Ready' : timeLeft(t.ready_at, now)}</span></li>
			{/each}
		</ul>
	{/if}
</section>

<style>
	ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
	li { display: flex; gap: 8px; align-items: center; }
	img { width: 28px; height: 28px; border-radius: 50%; }
	.label { flex: 1; }
	.ready { color: var(--accent); font-weight: 600; }
</style>
