<!-- frontend/src/lib/WishHistory.svelte -->
<script lang="ts">
	import { untrack } from 'svelte';
	import { api, errorMessage } from './api';
	import { imgSrc } from './img';
	import type { BannerRow, HistoryFilters, HistoryPage } from './types';
	import { POOLS, POOL_LABEL, loadFilters, saveFilters } from './wishes';

	let { banners, version }: { banners: BannerRow[]; version: number } = $props();
	let filters = $state<HistoryFilters>(loadFilters(() => localStorage));
	let page = $state(1);
	let data = $state<HistoryPage | null>(null);
	let error = $state<string | null>(null);
	const pages = $derived(data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1);

	let seq = 0;
	let qInput = $state(untrack(() => filters.q));
	let qTimer: ReturnType<typeof setTimeout> | undefined;

	$effect(() => {
		void version;
		const f = { ...filters };
		const p = page;
		saveFilters(() => localStorage, f);
		const mine = ++seq;
		api.wishHistory(f, p)
			.then((d) => { if (mine === seq) { data = d; error = null; } })
			.catch((e) => { if (mine === seq) error = errorMessage(e); });
	});

	$effect(() => () => clearTimeout(qTimer));

	function onSearch(value: string) {
		qInput = value;
		clearTimeout(qTimer);
		qTimer = setTimeout(() => set('q', value), 300);
	}

	function set<K extends keyof HistoryFilters>(key: K, value: HistoryFilters[K]) {
		filters = { ...filters, [key]: value };
		page = 1;
	}
</script>

<section class="panel">
	<h2>History</h2>
	<div class="filters">
		<select aria-label="Banner type" value={filters.pool}
			onchange={(e) => set('pool', e.currentTarget.value as HistoryFilters['pool'])}>
			<option value="">All banner types</option>
			{#each POOLS as p (p)}<option value={p}>{POOL_LABEL[p]}</option>{/each}
		</select>
		<select aria-label="Rarity" value={String(filters.rarity)}
			onchange={(e) => set('rarity', e.currentTarget.value === '' ? '' : Number(e.currentTarget.value))}>
			<option value="">All rarities</option>
			<option value="5">5★</option>
			<option value="4">4★</option>
			<option value="3">3★</option>
		</select>
		<select aria-label="Item type" value={filters.type}
			onchange={(e) => set('type', e.currentTarget.value as HistoryFilters['type'])}>
			<option value="">Characters and weapons</option>
			<option value="character">Characters</option>
			<option value="weapon">Weapons</option>
		</select>
		<select aria-label="Banner" value={filters.banner} onchange={(e) => set('banner', e.currentTarget.value)}>
			<option value="">All banners</option>
			{#each banners as b (b.key)}<option value={b.key}>{b.short_name} ({b.start.slice(0, 10)})</option>{/each}
		</select>
		<input type="search" placeholder="Search name" aria-label="Search name" value={qInput}
			oninput={(e) => onSearch(e.currentTarget.value)} />
	</div>
	{#if error}<p class="error">{error}</p>{/if}
	{#if data}
		<table>
			<thead><tr><th>Time</th><th>Item</th><th>★</th><th>Banner type</th><th>Banner</th><th>Pity</th></tr></thead>
			<tbody>
				{#each data.rows as r, i (`${r.time}-${r.name}-${i}`)}
					<tr data-testid="history-row" class="r{r.rarity}">
						<td>{r.time}</td>
						<td class="item">{#if imgSrc(r.icon)}<img src={imgSrc(r.icon)} alt="" />{/if}{r.name}</td>
						<td>{r.rarity}★</td>
						<td>{POOL_LABEL[r.pool]}</td>
						<td>{r.banner ?? '—'}</td>
						<td>{r.pity ?? ''}</td>
					</tr>
				{/each}
			</tbody>
		</table>
		{#if data.total === 0}<p class="muted">No pulls match these filters.</p>{/if}
		<div class="paging">
			<button type="button" onclick={() => (page = page - 1)} disabled={page <= 1}>Previous</button>
			<span class="muted">Page {page} of {pages} · {data.total} pulls</span>
			<button type="button" onclick={() => (page = page + 1)} disabled={page >= pages}>Next</button>
		</div>
	{/if}
</section>

<style>
	.filters { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
	table { width: 100%; border-collapse: collapse; font-size: 13px; }
	th, td { text-align: left; padding: 4px 10px 4px 0; border-bottom: 1px solid var(--line); }
	.item { display: flex; align-items: center; gap: 6px; }
	.item img { width: 24px; height: 24px; border-radius: 4px; background: var(--r0); }
	tr.r5 td { color: #e8c15a; }
	tr.r4 td { color: #b69be0; }
	.paging { display: flex; gap: 10px; align-items: center; margin-top: 10px; }
</style>
