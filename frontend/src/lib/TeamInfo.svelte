<script lang="ts">
	import TagChip from './TagChip.svelte';
	import { farmRows } from './teams';
	import type { GapStatus, Team } from './types';

	let { team, gaps, connected, drawerOpen, buildBusy = false, onBuild, onToggleDrawer }: {
		team: Team; gaps: GapStatus; connected: boolean; drawerOpen: boolean; buildBusy?: boolean;
		onBuild: (on: boolean) => void; onToggleDrawer: () => void;
	} = $props();

	const short = $derived(farmRows(team.shortfall ?? []).length);
	const pct = $derived(team.progress === null ? null : Math.round(team.progress * 100));
	const summary = $derived.by(() => {
		if (team.shortfall === null) return null;
		if (!connected) return 'Connect HoYoLAB to calculate';
		if (!gaps.computed_at) return 'Shortfall appears after the next sync';
		if (gaps.stale || gaps.pending) return 'Updating…';
		if (short > 0) return `${short} ${short === 1 ? 'material' : 'materials'} short`;
		return team.members.some((m) => m.not_calculated) ? 'Not calculated yet' : 'Ready ✓';
	});
</script>

<div class="info">
	<h2>{team.name}</h2>
	<label class="sw-row">
		<button type="button" role="switch" aria-checked={team.has_build_tag} aria-label="Build" class="sw" class:on={team.has_build_tag}
			aria-disabled={buildBusy} aria-busy={buildBusy} data-testid="build-switch-{team.id}" onclick={(e) => { e.stopPropagation(); if (!buildBusy) onBuild(!team.has_build_tag); }}></button>
		Build
	</label>
	<div class="tags">{#each team.tags.filter((t) => !t.builtin) as t (t.id)}<TagChip tag={t} />{/each}</div>
	{#if team.notes}<p class="notes">{team.notes}</p>{/if}
	{#if summary}
		<button type="button" class="link" data-testid="shortfall-toggle-{team.id}" aria-expanded={drawerOpen}
			onclick={(e) => { e.stopPropagation(); onToggleDrawer(); }}>
			{summary}{pct !== null ? ` · ${pct}%` : ''} {drawerOpen ? '▾' : '▸'}
		</button>
	{/if}
</div>

<style>
	.info { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
	h2 { margin: 0; font-size: 18px; color: var(--cream); overflow-wrap: anywhere; }
	.sw-row { display: flex; gap: 6px; align-items: center; font-size: 12px; }
	.sw { width: 32px; height: 18px; border-radius: 9px; padding: 0; border: 1px solid var(--glass-border); background: #3a3f50; position: relative; cursor: pointer; }
	.sw::after { content: ''; position: absolute; left: 2px; top: 2px; width: 12px; height: 12px; border-radius: 50%; background: var(--cream); transition: left 0.12s; }
	.sw.on { background: var(--gold); }
	.sw[aria-disabled='true'] { cursor: progress; opacity: 0.7; }
	.sw.on::after { left: 16px; background: #17130b; }
	.tags { display: flex; flex-wrap: wrap; gap: 4px; }
	.notes { margin: 0; font-size: 12px; color: var(--cream-dim, #b9ad95); white-space: pre-wrap; overflow: hidden;
		display: -webkit-box; -webkit-line-clamp: 3; line-clamp: 3; -webkit-box-orient: vertical; }
	.link { background: none; border: none; color: var(--accent); padding: 0; cursor: pointer; text-align: left; font-size: 12px; }
</style>
