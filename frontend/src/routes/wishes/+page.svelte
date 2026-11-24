<!-- frontend/src/routes/wishes/+page.svelte -->
<script lang="ts">
	import { onMount } from 'svelte';
	import BarChart from '$lib/BarChart.svelte';
	import FilterPill from '$lib/FilterPill.svelte';
	import Histogram from '$lib/Histogram.svelte';
	import LineChart from '$lib/LineChart.svelte';
	import PityPanel from '$lib/PityPanel.svelte';
	import RadarChart from '$lib/RadarChart.svelte';
	import WishHistory from '$lib/WishHistory.svelte';
	import { api, errorMessage } from '$lib/api';
	import { ELEMENTS, WEAPON_TYPES } from '$lib/charts';
	import { ELEMENT_STYLE } from '$lib/elements';
	import { imgSrc } from '$lib/img';
	import { timeAgo } from '$lib/time';
	import type { ImportStatus, Pool, WishFilter, WishSummary } from '$lib/types';
	import {
		FILTER_LABEL, POOL_LABEL, availableFilters, importResultLine, loadWishFilter, outcomeLabel, pickFilter,
		rotationBars, saveWishFilter, spiderSeries, stackedMonths, toFilter, verdictLabel
	} from '$lib/wishes';

	let data = $state<WishSummary | null>(null);
	let status = $state<ImportStatus | null>(null);
	let error = $state<string | null>(null);
	let toast = $state<string | null>(null);
	let filter = $state<WishFilter>('character');
	let byRotation = $state(false);
	let version = $state(0);
	let now = $state(Date.now());
	const running = $derived(status?.running ?? false);
	const filters = $derived(data ? availableFilters(data.analysis) : []);
	const block = $derived(data?.analysis[filter] ?? null);
	const elementAxes = ELEMENTS.map((e) => ({ label: e, icon: ELEMENT_STYLE[e].icon }));
	const weaponAxes = WEAPON_TYPES.map((w) => ({ label: w }));
	const pct = (n: number | null) => (n === null ? '—' : `${Math.round(n * 100)}%`);

	function radar(counts: { five: Record<string, number>; four: Record<string, number> }, axes: readonly string[]) {
		const s = spiderSeries(counts, axes);
		return [
			{ name: '5★', values: s.five, color: 'var(--rarity-5)' },
			{ name: '4★', values: s.four, color: 'var(--rarity-4)' }
		];
	}

	function choose(f: WishFilter) {
		filter = f;
		saveWishFilter(f);
	}

	async function load() {
		try {
			data = await api.wishSummary();
			status = data.import;
			filter = pickFilter(loadWishFilter(), availableFilters(data.analysis));
			error = null;
		} catch (e) {
			error = errorMessage(e);
		}
	}

	onMount(() => {
		load().then(() => {
			if (status?.running) void poll();
		});
		const t = setInterval(() => (now = Date.now()), 30_000);
		return () => clearInterval(t);
	});

	async function poll() {
		try {
			for (;;) {
				status = await api.importStatus();
				if (!status.running) break;
				await new Promise((r) => setTimeout(r, 2000));
			}
			await load();
			version++;
		} catch (e) {
			toast = errorMessage(e);
			status = { running: false, last: status?.last ?? null };
		}
	}

	async function importGame() {
		toast = null;
		try {
			await api.importGame();
			status = { running: true, last: status?.last ?? null };
			await poll();
		} catch (e) {
			toast = errorMessage(e);
		}
	}

	async function upload(e: Event) {
		const input = e.currentTarget as HTMLInputElement;
		const file = input.files?.[0];
		input.value = '';
		if (!file) return;
		toast = null;
		status = { running: true, last: status?.last ?? null };
		try {
			status = await api.uploadWishes(file);
		} catch (err) {
			toast = errorMessage(err);
		}
		await load();
		version++;
	}

	async function exportUigf() {
		toast = null;
		try {
			const res = await fetch('/api/wishes/export');
			if (!res.ok) {
				let detail = res.statusText;
				try {
					detail = (await res.json()).detail ?? detail;
				} catch {
					/* body was not JSON */
				}
				throw new Error(detail);
			}
			const name = /filename="([^"]+)"/.exec(res.headers.get('content-disposition') ?? '')?.[1]
				?? 'ad-astra-uigf.json';
			const a = document.createElement('a');
			a.href = URL.createObjectURL(await res.blob());
			a.download = name;
			a.click();
			URL.revokeObjectURL(a.href);
		} catch (e) {
			toast = errorMessage(e);
		}
	}

	async function setChart(pool: Pool, itemId: number | null) {
		if (!data) return;
		const before = data;
		data = {
			...data,
			pools: data.pools.map((p) => (p.pool === pool && p.fate ? { ...p, fate: { ...p.fate, chart_item_id: itemId } } : p))
		};
		try {
			const updated = await api.setChart(pool, itemId);
			data = { ...data, pools: data.pools.map((p) => (p.pool === pool ? updated : p)) };
		} catch (e) {
			data = before;
			toast = errorMessage(e);
		}
	}
</script>

<h1>Wishes</h1>
{#if error}<p class="error">{error}</p>{/if}
{#if toast}<p class="error" role="alert">{toast}</p>{/if}

<section class="panel header">
	<button type="button" class="primary" onclick={importGame} disabled={running}>
		{running ? 'Importing…' : 'Import from game'}
	</button>
	<label class="upload">
		<span>Upload file</span>
		<input type="file" accept=".json,.xlsx" onchange={upload} disabled={running} />
	</label>
	<button type="button" onclick={exportUigf} disabled={running}>Export UIGF</button>
	<span class="muted" data-testid="import-result">
		{#if running}<span class="spinner" aria-hidden="true"></span> Importing…
		{:else if status?.last}
			{importResultLine(status.last)}{status.last.finished_at ? ` · ${timeAgo(status.last.finished_at, now)}` : ''}
		{:else}No imports yet{/if}
	</span>
</section>

{#if data}
	{#if !data.banners_available && data.pools.length}
		<p class="muted">Banner data isn't downloaded yet, so 50/50 results show as Unknown until game data refreshes.</p>
	{/if}
	{#if data.pools.length === 0}
		<section class="panel empty">
			<h2>No wishes yet</h2>
			<ol>
				<li><strong>From the game:</strong> open Wish History in-game once (any banner), then press <em>Import from game</em>. Close the game first if the import says the cache is locked.</li>
				<li><strong>From paimon.moe:</strong> Settings → Export data (the .json backup) or Export to Excel (.xlsx), then <em>Upload file</em>.</li>
				<li><strong>From another tracker:</strong> export UIGF JSON, then <em>Upload file</em>.</li>
			</ol>
		</section>
	{:else}
		<div class="tiles">
			{#each data.pools as pool (pool.pool)}
				<PityPanel {pool} selected={filter === pool.pool} onselect={() => choose(toFilter(pool.pool))}
					onChart={(id) => setChart(pool.pool, id)} />
			{/each}
		</div>

		<div class="pills" data-testid="filters" role="group" aria-label="Banner filter">
			{#each filters as f (f)}
				<FilterPill label={FILTER_LABEL[f]} on={filter === f} onclick={() => choose(f)} color="var(--avg-pity)" />
			{/each}
		</div>

		{#if block}
			<div class="row two">
				<section class="panel" data-testid="pulls-chart">
					<div class="head">
						<h2>Pulls per {byRotation ? 'rotation' : 'month'}</h2>
						<div class="toggle" role="group" aria-label="Group pulls by">
							<button type="button" aria-pressed={!byRotation} onclick={() => (byRotation = false)}>Month</button>
							<button type="button" aria-pressed={byRotation} onclick={() => (byRotation = true)}>Rotation</button>
						</div>
					</div>
					{#if byRotation && block.rotations.length === 0}
						<p class="muted">No pulls are matched to banners yet.</p>
					{:else}
						<BarChart title="" bars={byRotation ? rotationBars(block.rotations) : stackedMonths(block.months)} />
					{/if}
					{#if byRotation}
						<div class="rot-fives">
							{#each block.rotations.filter((r) => r.fives.length) as r (r.label)}
								<span class="muted">{r.label}</span>
								{#each r.fives as f, i (i)}{#if imgSrc(f.icon)}<img src={imgSrc(f.icon)} alt={f.name} title={f.name} />{/if}{/each}
							{/each}
						</div>
					{/if}
				</section>
				<section class="panel luck" data-testid="luck">
					<h2>Luck</h2>
					{#if block.luck.avg_pity === null}
						<p class="muted">No 5★ yet.</p>
					{:else}
						<div class="big">{block.luck.avg_pity}<span class="muted">&nbsp;avg 5★ pity</span></div>
						<div class="muted">expected ≈ {block.luck.expected} (estimate) · <strong>{verdictLabel(block.luck.verdict)}</strong></div>
					{/if}
					{#if block.luck.judged_label}
						<div class="big">{pct(block.luck.rate)}<span class="muted">&nbsp;{block.luck.judged_label} won ({block.luck.won} of {(block.luck.won ?? 0) + (block.luck.lost ?? 0)})</span></div>
					{/if}
				</section>
			</div>

			<div class="row three">
				<section class="panel">
					<RadarChart testid="elements-radar" title="Elements pulled" axes={elementAxes} series={radar(block.elements, ELEMENTS)} />
					{#if block.unknown_items}<p class="muted small">{block.unknown_items} pull(s) not in game data yet are left out.</p>{/if}
				</section>
				<section class="panel">
					<RadarChart testid="weapons-radar" title="Weapon types" axes={weaponAxes} series={radar(block.weapon_types, WEAPON_TYPES)} />
				</section>
				<section class="panel">
					<Histogram buckets={block.pity_hist.buckets} soft={block.pity_hist.soft} avg={block.pity_hist.avg} />
				</section>
			</div>

			<section class="panel">
				<LineChart points={block.primogems.points} marks={block.primogems.fives} />
			</section>

			<section class="panel">
				<h2>5★ pulled · {FILTER_LABEL[filter]}</h2>
				{#if block.fives.length === 0}<p class="muted">No 5★ yet.</p>{/if}
				<ul class="pulls" data-testid="five-list">
					{#each block.fives as p, i (`${p.time}-${i}`)}
						<li class="r5">
							{#if imgSrc(p.icon)}<img src={imgSrc(p.icon)} alt="" />{/if}
							<span class="name">{p.name}</span>
							<span class="pity">{p.pity}</span>
							{#if p.outcome}<span class="badge {p.outcome}">{outcomeLabel(p.outcome)}</span>{/if}
							{#if filter === 'all'}<span class="badge">{POOL_LABEL[p.pool as Pool]}</span>{/if}
							<span class="muted">{p.banner ?? ''} · {p.time.slice(0, 10)}</span>
						</li>
					{/each}
				</ul>
				<h2>4★</h2>
				{#if block.fours.length === 0}<p class="muted">No 4★ yet.</p>{/if}
				<ul class="pulls compact" data-testid="four-list">
					{#each block.fours as p, i (`${p.time}-${i}`)}
						<li><span class="name">{p.name}</span><span class="pity">{p.pity}</span>
							<span class="muted">{p.time.slice(0, 10)}</span></li>
					{/each}
				</ul>
			</section>
		{/if}

		<WishHistory banners={data.banners} {version} />
	{/if}
{/if}

<style>
	.header { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
	.upload { display: inline-flex; align-items: center; gap: 6px; cursor: pointer; }
	.upload input { max-width: 220px; }
	.tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 12px; margin: 12px 0; }
	.pills { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
	.row { display: grid; gap: 12px; margin-bottom: 12px; }
	.row.two { grid-template-columns: 2fr 1fr; }
	.row.three { grid-template-columns: 1fr 1fr 1.3fr; }
	@media (max-width: 900px) { .row.two, .row.three { grid-template-columns: 1fr; } }
	section.panel { margin-top: 0; margin-bottom: 12px; }
	.row section.panel { margin-bottom: 0; }
	.head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
	.toggle { display: inline-flex; gap: 4px; }
	.toggle button[aria-pressed='true'] { border-color: var(--avg-pity); color: var(--avg-pity); }
	.rot-fives { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; margin-top: 6px; font-size: 11px; }
	.rot-fives img { width: 22px; height: 22px; border-radius: 50%; }
	.luck .big { font-size: 24px; font-weight: 700; margin-top: 4px; }
	.luck .big .muted { font-size: 13px; font-weight: 400; }
	.small { font-size: 11px; }
	.empty ol { margin: 0; padding-left: 20px; display: grid; gap: 6px; }
	.spinner { display: inline-block; width: 10px; height: 10px; border: 2px solid var(--muted);
		border-top-color: transparent; border-radius: 50%; animation: spin 0.8s linear infinite; }
	@keyframes spin { to { transform: rotate(360deg); } }
	.pulls { list-style: none; padding: 0; margin: 0 0 12px; display: grid; gap: 6px; }
	.pulls li { display: flex; align-items: center; gap: 10px; }
	.pulls img { width: 32px; height: 32px; border-radius: 6px; background: var(--r5); }
	.pulls .name { min-width: 180px; font-weight: 600; }
	.pulls .pity { min-width: 28px; text-align: right; font-variant-numeric: tabular-nums; }
	.pulls.compact { grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); }
	.pulls.compact .name { min-width: 150px; font-weight: 400; }
	.badge { font-size: 11px; padding: 1px 6px; border-radius: 8px; background: var(--panel-2); border: 1px solid var(--line); }
	.badge.won, .badge.charted { color: var(--building); border-color: var(--building); }
	.badge.lost, .badge.not_charted { color: var(--error); border-color: var(--error); }
	.badge.guaranteed { color: var(--wanted); border-color: var(--wanted); }
</style>
