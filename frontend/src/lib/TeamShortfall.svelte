<script lang="ts">
	import { gapLabel, gapsSettled } from './materials';
	import MaterialTile from './MaterialTile.svelte';
	import { farmRows, teamTileView } from './teams';
	import type { GapStatus, Team } from './types';

	let { team, gaps, connected, now }: { team: Team; gaps: GapStatus; connected: boolean; now: number } = $props();
	const rows = $derived(farmRows(team.shortfall ?? []));
	const anyNotCalculated = $derived(team.members.some((m) => m.not_calculated));
</script>

<section class="shortfall" data-testid="team-shortfall-{team.id}">
	{#if !connected}
		<p class="muted">Connect HoYoLAB to calculate</p>
	{:else if !gaps.computed_at}
		<p class="muted">Shortfall appears after the next sync</p>
	{:else}
		{#if gaps.stale || gaps.pending || gaps.ok === false}<p class="muted">{gapLabel(gaps, now)}</p>{/if}
		{#if rows.length > 0}
			<div class="tiles">
				{#each rows as r (r.id)}
					<MaterialTile name={r.name} icon={r.icon} rarity={r.rarity} view={teamTileView(r)} testid="team-{team.id}-tile-{r.id}" />
				{/each}
			</div>
		{:else if !anyNotCalculated && gapsSettled(gaps)}
			<p class="ok">Everything in the bag ✓</p>
		{:else}
			<p class="muted">Not calculated yet</p>
		{/if}
	{/if}
</section>

<style>
	.shortfall { padding: 10px 16px 14px; border-top: 1px solid var(--glass-border); }
	.tiles { display: flex; flex-wrap: wrap; gap: 8px; }
	.ok { color: var(--accent); }
</style>
