<script lang="ts">
	import { api, errorMessage } from '$lib/api';
	import MaterialPopover from '$lib/MaterialPopover.svelte';
	import MaterialTile from '$lib/MaterialTile.svelte';
	import { filterMaterials, gapLabel, shouldPoll, tileView, type InventoryFilter } from '$lib/materials';
	import { sync } from '$lib/sync.svelte';
	import type { Inventory } from '$lib/types';

	const FILTER_KEY = 'gt.inventory.filter';
	const FILTERS: { key: InventoryFilter; label: string }[] = [
		{ key: 'all', label: 'All' },
		{ key: 'needed', label: 'Needed' },
		{ key: 'farm', label: 'To farm' }
	];

	function readFilter(): InventoryFilter {
		try {
			const v = localStorage.getItem(FILTER_KEY);
			return v === 'needed' || v === 'farm' ? v : 'all';
		} catch {
			return 'all';
		}
	}

	let data = $state<Inventory | null>(null);
	let error = $state<string | null>(null);
	let filter = $state<InventoryFilter>(readFilter());
	let query = $state('');
	let now = $state(Date.now());

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
			.map((c) => ({ ...c, shown: filterMaterials(c.materials, filter, query) }))
			.filter((c) => c.shown.length > 0)
	);
	const anyNeeded = $derived((data?.categories ?? []).some((c) => c.materials.some((m) => m.state !== 'unneeded')));
</script>

<h1>Inventory</h1>
{#if error}<p class="error">{error}</p>{/if}

{#if data}
	<div class="bar">
		<div class="chips">
			{#each FILTERS as f (f.key)}
				<button type="button" class="chip" class:on={filter === f.key} onclick={() => setFilter(f.key)}>{f.label}</button>
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
						dim={m.state === 'unneeded'} testid="tile-{m.id}">
						{#snippet popover()}<MaterialPopover material={m} />{/snippet}
					</MaterialTile>
				{/each}
			</div>
		</section>
	{/each}
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
