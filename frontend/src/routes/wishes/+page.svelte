<!-- frontend/src/routes/wishes/+page.svelte -->
<script lang="ts">
	import { onMount } from 'svelte';
	import { api, errorMessage } from '$lib/api';
	import PityPanel from '$lib/PityPanel.svelte';
	import { timeAgo } from '$lib/time';
	import type { ImportStatus, Pool, WishSummary } from '$lib/types';
	import { POOL_LABEL, importResultLine } from '$lib/wishes';

	let data = $state<WishSummary | null>(null);
	let status = $state<ImportStatus | null>(null);
	let error = $state<string | null>(null);
	let toast = $state<string | null>(null);
	let tab = $state<Pool>('character');
	let version = $state(0);
	let now = $state(Date.now());
	const running = $derived(status?.running ?? false);

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
		for (;;) {
			status = await api.importStatus();
			if (!status.running) break;
			await new Promise((r) => setTimeout(r, 2000));
		}
		await load();
		version++;
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
			if (!res.ok) throw new Error((await res.json()).detail ?? res.statusText);
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
		<!-- Task 17: tabs, charts, history -->
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
</style>
