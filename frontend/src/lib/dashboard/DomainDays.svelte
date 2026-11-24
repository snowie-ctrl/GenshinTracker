<script lang="ts">
	import MaterialPopover from '$lib/MaterialPopover.svelte';
	import MaterialTile from '$lib/MaterialTile.svelte';
	import { DAY_LABELS, dayButtons } from '$lib/dashboard';
	import { imgSrc } from '$lib/img';
	import { gapsSettled, notCalculatedLabel, tileView } from '$lib/materials';
	import type { DayFarm, GapStatus } from '$lib/types';

	let { days, today, hasBuilds, gaps, now }: {
		days: Record<string, DayFarm>; today: number; hasBuilds: boolean; gaps: GapStatus; now: number;
	} = $props();
	let viewed = $state<number | null>(null);
	const shown = $derived(viewed ?? today);
	const buttons = $derived(dayButtons(shown, today));
	const domains = $derived(days[String(shown)]?.domains ?? []);
</script>

<section class="panel" data-testid="domains">
	<div class="head">
		<h2>Domains</h2>
		<div class="days" role="group" aria-label="Day">
			{#each buttons as b (b.day)}
				<button type="button" class="day" class:viewed={b.viewed} class:today={b.today} aria-pressed={b.viewed}
					data-testid="day-{b.day}" onclick={() => (viewed = b.day)}>{b.label}</button>
			{/each}
			<button type="button" class="day" onclick={() => (viewed = null)} disabled={shown === today}>Today</button>
		</div>
	</div>
	{#if !hasBuilds}
		<p class="muted">Mark characters as Build on <a href="/characters">Characters</a> to plan farming.</p>
	{:else if domains.length === 0}
		<p class="muted">{gapsSettled(gaps) ? `Nothing to farm on ${DAY_LABELS[shown]}` : notCalculatedLabel(gaps, now)}</p>
	{:else}
		<div class="cards">
			{#each domains as d (d.id)}
				<div class="card">
					<div class="title">{d.name}</div>
					<div class="tiles-row">
						{#each d.materials as m (m.id)}
							<MaterialTile name={m.name} icon={m.icon} rarity={m.rarity} view={tileView(m)}>
								{#snippet popover()}<MaterialPopover material={m} />{/snippet}
							</MaterialTile>
						{/each}
					</div>
					<div class="avatars">
						{#each d.characters as c (c.id)}
							<a href="/characters/{c.slug}" title={c.name}>{#if imgSrc(c.icon)}<img src={imgSrc(c.icon)} alt={c.name} />{/if}</a>
						{/each}
					</div>
				</div>
			{/each}
		</div>
	{/if}
</section>

<style>
	.head { display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: center; justify-content: space-between; }
	.head h2 { margin: 0; }
	.days { display: flex; flex-wrap: wrap; gap: 4px; }
	.day { border: 1px solid var(--glass-border); background: transparent; color: var(--text); border-radius: 999px; padding: 3px 10px; cursor: pointer; }
	.day.today { border-color: var(--gold); color: var(--gold); }
	.day.viewed { background: var(--accent); border-color: var(--accent); color: var(--bg); }
	.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; margin-top: 10px; }
	.card { background: var(--panel-2); border: 1px solid var(--line); border-radius: 10px; padding: 10px; }
	.title { font-weight: 600; }
	.tiles-row { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0; }
	.avatars { display: flex; gap: 4px; }
	.avatars img { width: 28px; height: 28px; border-radius: 50%; background: var(--r0); }
</style>
