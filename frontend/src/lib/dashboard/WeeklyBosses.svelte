<script lang="ts">
	import MaterialPopover from '$lib/MaterialPopover.svelte';
	import MaterialTile from '$lib/MaterialTile.svelte';
	import { api, errorMessage } from '$lib/api';
	import { imgSrc } from '$lib/img';
	import { gapsSettled, notCalculatedLabel, tileView } from '$lib/materials';
	import type { GapStatus, WeeklyBoss } from '$lib/types';

	let { weekly, hasBuilds, gaps, now }: {
		weekly: { discounts_left: number | null; discounts_max: number | null; bosses: WeeklyBoss[] };
		hasBuilds: boolean; gaps: GapStatus; now: number;
	} = $props();
	let toast = $state<string | null>(null);
	let overrides = $state<Record<string, boolean>>({});
	// Drop an override once the server agrees with it, so later server changes win.
	$effect(() => {
		const stale = weekly.bosses.filter((b) => b.name in overrides && overrides[b.name] === b.done);
		if (stale.length === 0) return;
		const next = { ...overrides };
		for (const b of stale) delete next[b.name];
		overrides = next;
	});
	const bosses = $derived(weekly.bosses.map((b) => ({ ...b, done: overrides[b.name] ?? b.done }))
		.sort((a, b) => Number(a.done) - Number(b.done)));

	async function toggle(b: WeeklyBoss) {
		const done = !b.done;
		overrides = { ...overrides, [b.name]: done };
		try {
			await api.setBossDone(b.name, done);
			toast = null;
		} catch (e) {
			overrides = { ...overrides, [b.name]: !done };
			toast = errorMessage(e);
		}
	}
</script>

<section class="panel" data-testid="weekly-bosses">
	<h2>Weekly bosses {#if weekly.discounts_left !== null}<span class="muted small">Discounts {weekly.discounts_left}/{weekly.discounts_max} left</span>{/if}</h2>
	{#if toast}<p class="error">{toast}</p>{/if}
	{#if !hasBuilds}
		<p class="muted">Mark characters as Build on <a href="/characters">Characters</a> to plan farming.</p>
	{:else if bosses.length === 0}
		<p class="muted">{gapsSettled(gaps) ? 'No weekly boss drops to farm ✓' : notCalculatedLabel(gaps, now)}</p>
	{:else}
		<div class="cards">
			{#each bosses as b (b.name)}
				<div class="card" class:done={b.done} data-testid="boss-{b.name}">
					<label class="title"><input type="checkbox" checked={b.done} onchange={() => toggle(b)} aria-label="Done this week" />{b.name}</label>
					<div class="tiles-row">
						{#each b.materials as m (m.id)}
							<MaterialTile name={m.name} icon={m.icon} rarity={m.rarity} view={tileView(m)}>
								{#snippet popover()}<MaterialPopover material={m} />{/snippet}
							</MaterialTile>
						{/each}
					</div>
					<div class="avatars">
						{#each b.characters as c (c.id)}
							<a href="/characters/{c.slug}" title={c.name}>{#if imgSrc(c.icon)}<img src={imgSrc(c.icon)} alt={c.name} />{/if}</a>
						{/each}
					</div>
				</div>
			{/each}
		</div>
	{/if}
</section>

<style>
	.small { font-size: 13px; font-weight: 400; margin-left: 8px; }
	.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; }
	.card { background: var(--panel-2); border: 1px solid var(--line); border-radius: 10px; padding: 10px; }
	.card.done { opacity: 0.45; }
	.title { font-weight: 600; display: flex; gap: 6px; align-items: center; }
	.tiles-row { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0; }
	.avatars { display: flex; gap: 4px; }
	.avatars img { width: 28px; height: 28px; border-radius: 50%; background: var(--r0); }
</style>
