<!-- frontend/src/lib/PityPanel.svelte -->
<script lang="ts">
	import type { PoolSummary } from './types';
	import { POOL_LABEL, fateLine, pityBar, radianceLine } from './wishes';

	let { pool, selected, onselect, onChart }: {
		pool: PoolSummary; selected: boolean; onselect: () => void; onChart: (itemId: number | null) => void;
	} = $props();
	const bar = $derived(pityBar(pool.pity5, pool.hard, pool.soft, pool.avg_pity));

	function change(e: Event) {
		const v = (e.currentTarget as HTMLSelectElement).value;
		onChart(v === '' ? null : Number(v));
	}
</script>

<section class="panel pity" class:selected data-testid="pity-{pool.pool}">
	<h2>
		<button type="button" class="title" aria-pressed={selected} onclick={onselect}>{POOL_LABEL[pool.pool]}</button>
		{#if pool.next_state === 'guaranteed'}
			<span class="up" data-testid="guaranteed" title="Next 5★ is guaranteed" aria-label="Next 5★ is guaranteed">▲</span>
		{/if}
	</h2>
	<div class="big">{pool.pity5}<span class="muted">&nbsp;/ {pool.hard}</span></div>
	<div class="bar" role="progressbar" aria-label="5★ pity" aria-valuenow={pool.pity5} aria-valuemin={0}
		aria-valuemax={pool.hard}>
		<span class="fill" class:soft={pool.in_soft} style="width: {bar.fill}%"></span>
		{#if bar.soft !== null}<span class="mark" style="left: {bar.soft}%" title="Soft pity from {pool.soft}"></span>{/if}
		{#if bar.avg !== null}
			<span class="mark avg" data-testid="avg-mark" style="left: {bar.avg}%" title="Your average 5★ pity: {pool.avg_pity}"></span>
		{/if}
	</div>
	<div class="muted small">4★ pity {pool.pity4} / 10{pool.in_soft ? ' · in soft pity' : ''}{pool.avg_pity !== null ? ` · avg 5★ at ${pool.avg_pity}` : ''}</div>
	<div class="bar bar4" role="progressbar" aria-label="4★ pity" aria-valuenow={pool.pity4} aria-valuemin={0}
		aria-valuemax={10}>
		<span class="fill four" style="width: {Math.min(100, (pool.pity4 / 10) * 100)}%"></span>
	</div>
	{#if pool.radiance}
		<div class="muted small" title="Community estimate: the game does not show this counter.">
			{radianceLine(pool.radiance)}
			· <a href="https://genshin-impact.fandom.com/wiki/Wish#Capturing_Radiance" target="_blank"
				rel="noopener">about Capturing Radiance</a>
		</div>
	{/if}
	{#if pool.fate}
		<label class="small">
			{pool.pool === 'weapon' ? 'Charted weapon' : 'Charted item'}
			<select onchange={change} value={pool.fate.chart_item_id ?? ''} disabled={pool.fate.choices.length === 0}>
				<option value="">None</option>
				{#each pool.fate.choices as c (c.item_id)}<option value={c.item_id}>{c.name}</option>{/each}
			</select>
		</label>
		<div class="small" data-testid="fate">{fateLine(pool.fate, pool.pool)}</div>
	{/if}
</section>

<style>
	.pity { min-width: 220px; display: flex; flex-direction: column; gap: 6px; }
	.big { font-size: 28px; font-weight: 700; }
	.big .muted { font-size: 16px; font-weight: 400; }
	.bar { position: relative; height: 8px; background: var(--line); border-radius: 4px; }
	.fill { display: block; height: 100%; border-radius: 4px; background: var(--accent); }
	.fill.soft { background: var(--warn); }
	.bar4 { height: 4px; }
	.fill.four { background: var(--muted); }
	.mark { position: absolute; top: -3px; width: 2px; height: 14px; background: var(--warn); }
	.pity.selected { border-color: var(--avg-pity); }
	h2 { display: flex; align-items: center; gap: 6px; margin: 0; }
	.title { all: unset; cursor: pointer; font: inherit; }
	.title:focus-visible { outline: 2px solid var(--avg-pity); outline-offset: 2px; border-radius: 4px; }
	.up { color: var(--rarity-5); font-size: 15px; line-height: 1; }
	.mark.avg { background: var(--avg-pity); }
	.small { font-size: 12px; }
	label { display: flex; flex-direction: column; gap: 4px; color: var(--muted); }
</style>
