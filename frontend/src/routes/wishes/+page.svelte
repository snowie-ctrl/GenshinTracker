<!-- frontend/src/routes/wishes/+page.svelte -->
<script lang="ts">
	import { onMount } from 'svelte';
	import BarChart from '$lib/BarChart.svelte';
	import WishHistory from '$lib/WishHistory.svelte';
	import { imgSrc } from '$lib/img';
	import { api, errorMessage } from '$lib/api';
	import PityPanel from '$lib/PityPanel.svelte';
	import { timeAgo } from '$lib/time';
	import type { ImportStatus, Pool, WishSummary } from '$lib/types';
	import { POOL_COLOR, POOL_LABEL, histogramBars, importResultLine, outcomeLabel, scaleTo, stackedMonths } from '$lib/wishes';

	let data = $state<WishSummary | null>(null);
	let status = $state<ImportStatus | null>(null);
	let error = $state<string | null>(null);
	let toast = $state<string | null>(null);
	let tab = $state<Pool>('character');
	let version = $state(0);
	let now = $state(Date.now());
	const running = $derived(status?.running ?? false);
	const current = $derived(data?.pools.find((p) => p.pool === tab) ?? null);
	const bannerWidths = $derived(data ? scaleTo(data.charts.banners.map((b) => b.pulls), 100) : []);
	const pct = (n: number | null) => (n === null ? '—' : `${Math.round(n * 100)}%`);

	async function load() {
		try {
			data = await api.wishSummary();
			status = data.import;
			if (data.pools.length && !data.pools.some((p) => p.pool === tab)) tab = data.pools[0].pool;
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
				?? 'genshintracker-uigf.json';
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
				<li><strong>From paimon.moe:</strong> Settings → Export to Excel, then <em>Upload file</em> with the .xlsx.</li>
				<li><strong>From another tracker:</strong> export UIGF JSON, then <em>Upload file</em>.</li>
			</ol>
		</section>
	{:else}
		<div class="panels">
			{#each data.pools as pool (pool.pool)}
				<PityPanel {pool} onChart={(id) => setChart(pool.pool, id)} />
			{/each}
		</div>
		<div class="tabs" role="tablist" aria-label="Banner type">
			{#each data.pools as p (p.pool)}
				<button type="button" role="tab" aria-selected={tab === p.pool} class:active={tab === p.pool}
					onclick={() => (tab = p.pool)}>{POOL_LABEL[p.pool]}</button>
			{/each}
		</div>
		{#if current}
			<section class="panel" role="tabpanel" data-testid="tab-{current.pool}">
				<div class="stats">
					<div><span class="muted">Pulls</span><strong>{current.stats.pulls}</strong></div>
					<div><span class="muted">Primogems</span><strong>{current.stats.primogems.toLocaleString()}</strong></div>
					<div><span class="muted">5★</span><strong>{current.stats.five}</strong></div>
					<div><span class="muted">Average 5★ pity</span><strong>{current.stats.avg_five_pity ?? '—'}</strong></div>
					{#if current.pool === 'character' || current.pool === 'weapon'}
						<div><span class="muted">{current.pool === 'weapon' ? '75/25' : '50/50'} win rate</span>
							<strong>{pct(current.stats.win_rate)}</strong></div>
					{/if}
				</div>
				<h2>5★</h2>
				{#if current.fives.length === 0}<p class="muted">No 5★ yet.</p>{/if}
				<ul class="pulls">
					{#each current.fives as p, i (`${p.time}-${i}`)}
						<li class="r5">
							{#if imgSrc(p.icon)}<img src={imgSrc(p.icon)} alt="" />{/if}
							<span class="name">{p.name}</span>
							<span class="pity">{p.pity}</span>
							{#if p.outcome}<span class="badge {p.outcome}">{outcomeLabel(p.outcome)}</span>{/if}
							<span class="muted">{p.banner ?? ''} · {p.time.slice(0, 10)}</span>
						</li>
					{/each}
				</ul>
				<h2>4★</h2>
				{#if current.fours.length === 0}<p class="muted">No 4★ yet.</p>{/if}
				<ul class="pulls compact">
					{#each current.fours as p, i (`${p.time}-${i}`)}
						<li><span class="name">{p.name}</span><span class="pity">{p.pity}</span>
							<span class="muted">{p.time.slice(0, 10)}</span></li>
					{/each}
				</ul>
			</section>
		{/if}

		<section class="panel charts">
			<BarChart title="Pulls per month" bars={stackedMonths(data.charts.monthly)} />
			<BarChart title="5★ pity" bars={histogramBars(data.charts.pity_histogram)} />
		</section>

		<section class="panel">
			<h2>Banners</h2>
			{#if data.charts.banners.length === 0}<p class="muted">No pulls are matched to banners yet.</p>{/if}
			<ul class="timeline">
				{#each data.charts.banners as b, i (b.key)}
					<li>
						<span class="bname">{b.short_name} <span class="muted">{b.start.slice(0, 10)}</span></span>
						<span class="track"><span style="width: {bannerWidths[i]}%; background: {POOL_COLOR[b.pool]}"></span></span>
						<span>{b.pulls}</span>
						<span class="muted">{b.fives.join(', ')}</span>
					</li>
				{/each}
			</ul>
		</section>

		<WishHistory banners={data.charts.banners} {version} />
	{/if}
{/if}

<style>
	.header { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
	.upload { display: inline-flex; align-items: center; gap: 6px; cursor: pointer; }
	.upload input { max-width: 220px; }
	.panels { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 12px; margin: 12px 0; }
	.empty ol { margin: 0; padding-left: 20px; display: grid; gap: 6px; }
	.spinner { display: inline-block; width: 10px; height: 10px; border: 2px solid var(--muted);
		border-top-color: transparent; border-radius: 50%; animation: spin 0.8s linear infinite; }
	@keyframes spin { to { transform: rotate(360deg); } }
	section.panel { margin-top: 12px; }
	.tabs { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; }
	.tabs button.active { border-color: var(--accent); color: var(--accent); }
	.stats { display: flex; flex-wrap: wrap; gap: 24px; margin-bottom: 10px; }
	.stats div { display: flex; flex-direction: column; }
	.stats strong { font-size: 20px; }
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
	.charts { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; }
	.timeline { list-style: none; padding: 0; margin: 0; display: grid; gap: 4px; }
	.timeline li { display: grid; grid-template-columns: 220px 1fr 50px 2fr; gap: 10px; align-items: center; font-size: 13px; }
	.track { height: 8px; background: var(--line); border-radius: 4px; overflow: hidden; }
	.track span { display: block; height: 100%; }
</style>
