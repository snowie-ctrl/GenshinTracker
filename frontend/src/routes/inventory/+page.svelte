<script lang="ts">
	import { api, errorMessage } from '$lib/api';
	import MaterialPopover from '$lib/MaterialPopover.svelte';
	import MaterialTile from '$lib/MaterialTile.svelte';
	import { filterMaterials, gapLabel, shouldPoll, tileDim, tileView, type InventoryFilter } from '$lib/materials';
	import { sync } from '$lib/sync.svelte';
	import { scanAgeNote } from '$lib/good';
	import { timeAgo } from '$lib/time';
	import GoodImportButton from '$lib/GoodImportButton.svelte';
	import WeaponsTab from '$lib/WeaponsTab.svelte';
	import ArtifactsTab from '$lib/ArtifactsTab.svelte';
	import type { Inventory } from '$lib/types';

	const FILTER_KEY = 'gt.inventory.filter';
	const BASE_FILTERS: { key: InventoryFilter; label: string }[] = [
		{ key: 'all', label: 'All' },
		{ key: 'needed', label: 'Needed' },
		{ key: 'farm', label: 'To farm' }
	];

	function readFilter(): InventoryFilter {
		try {
			const v = localStorage.getItem(FILTER_KEY);
			return v === 'needed' || v === 'farm' || v === 'owned' ? v : 'all';
		} catch {
			return 'all';
		}
	}

	let data = $state<Inventory | null>(null);
	let error = $state<string | null>(null);
	let filter = $state<InventoryFilter>(readFilter());
	let query = $state('');
	let now = $state(Date.now());

	const filters = $derived(data?.good ? [...BASE_FILTERS, { key: 'owned' as const, label: 'Owned' }] : BASE_FILTERS);
	const activeFilter = $derived(filter === 'owned' && !data?.good ? 'all' : filter);

	type Tab = 'materials' | 'weapons' | 'artifacts';
	const TAB_KEY = 'gt.inventory.tab';
	function readTab(): Tab {
		try {
			const v = localStorage.getItem(TAB_KEY);
			return v === 'weapons' || v === 'artifacts' ? v : 'materials';
		} catch {
			return 'materials';
		}
	}
	let tab = $state<Tab>(readTab());
	const activeTab = $derived<Tab>(data?.good ? tab : 'materials');
	function setTab(t: Tab) {
		tab = t;
		try {
			localStorage.setItem(TAB_KEY, t);
		} catch {
			/* remembered tab is a convenience only */
		}
	}
	let goodEnabled = $state(false);
	$effect(() => {
		void sync.version;
		api.settings().then((s) => (goodEnabled = s.good_import_enabled)).catch(() => {});
	});

	function setFilter(f: InventoryFilter) {
		filter = f;
		try {
			localStorage.setItem(FILTER_KEY, f);
		} catch {
			/* remembered filter is a convenience only */
		}
	}

	async function load() {
		try {
			data = await api.inventory();
			error = null;
			now = Date.now();
		} catch (e) {
			error = errorMessage(e);
		}
	}

	$effect(() => {
		void sync.version;
		load();
	});

	$effect(() => {
		if (!shouldPoll(data?.gaps)) return;
		const t = setTimeout(load, 2000);
		return () => clearTimeout(t);
	});

	const sections = $derived(
		(data?.categories ?? [])
			.map((c) => ({ ...c, shown: filterMaterials(c.materials, activeFilter, query) }))
			.filter((c) => c.shown.length > 0)
	);
	const anyNeeded = $derived((data?.categories ?? []).some((c) => c.materials.some((m) => m.state !== 'unneeded')));
</script>

<h1>Inventory</h1>
{#if error}<p class="error">{error}</p>{/if}

{#if data}
	{#if data.good || goodEnabled}
		<div class="bar">
			{#if data.good}
				<div role="tablist" class="chips">
					{#each [['materials', 'Materials'], ['weapons', 'Weapons'], ['artifacts', 'Artifacts']] as [key, label] (key)}
						<button type="button" role="tab" class="chip" class:on={activeTab === key}
							aria-selected={activeTab === key} onclick={() => setTab(key as Tab)}>{label}</button>
					{/each}
				</div>
			{/if}
			{#if goodEnabled}<GoodImportButton onimported={load} />{/if}
			{#if data.good}
				<span class="muted" data-testid="scan-status">Scan: {new Date(data.good.imported_at).toLocaleDateString()}
					({timeAgo(data.good.imported_at, now)}){data.good.source ? ` from ${data.good.source}` : ''}
					{#if scanAgeNote(data.good.imported_at, now)} · ⚠ {scanAgeNote(data.good.imported_at, now)}{/if}</span>
			{/if}
		</div>
	{/if}

	{#if activeTab === 'materials'}
		<div class="bar">
			<div class="chips">
				{#each filters as f (f.key)}
					<button type="button" class="chip" class:on={activeFilter === f.key} onclick={() => setFilter(f.key)}>{f.label}</button>
				{/each}
			</div>
			<input type="search" placeholder="Search materials" aria-label="Search materials" bind:value={query} />
			<span class="muted status" data-testid="gap-status">{gapLabel(data.gaps, now)}</span>
		</div>
		{#if data.gaps.skipped.length}
			<p class="muted">{data.gaps.skipped.join(', ')} planning isn't supported yet.</p>
		{/if}
		{#if !anyNeeded}<p class="muted">Set characters to Build to plan farming.</p>{/if}

		{#each sections as c (c.key)}
			<section class="panel" data-testid="category-{c.key}">
				<h2>{c.label}</h2>
				<div class="grid">
					{#each c.shown as m (m.id)}
						<MaterialTile name={m.name} icon={m.icon} rarity={m.rarity} view={tileView(m)}
							dim={tileDim(m)} testid="tile-{m.id}">
							{#snippet popover()}<MaterialPopover material={m} scannedAt={data?.good?.imported_at ?? null} />{/snippet}
						</MaterialTile>
					{/each}
				</div>
			</section>
		{/each}
	{:else if activeTab === 'weapons' && data.good}
		<WeaponsTab version={data.good.imported_at} />
	{:else if data.good}
		<ArtifactsTab version={data.good.imported_at} />
	{/if}
{:else if !error}
	<p class="muted">Loading…</p>
{/if}

<style>
	.bar { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-bottom: 12px; }
	.chips { display: flex; gap: 6px; }
	.status { margin-left: auto; }
	section { margin-bottom: 12px; }
	.grid { display: flex; flex-wrap: wrap; gap: 10px; }
</style>
