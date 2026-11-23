<script lang="ts">
	import TeamInfo from './TeamInfo.svelte';
	import TeamRibbon from './TeamRibbon.svelte';
	import TeamShortfall from './TeamShortfall.svelte';
	import { MAX_MEMBERS, slantInset } from './teams';
	import type { GapStatus, Team, TeamMember } from './types';

	let { team, gaps, connected, now, reorderable, first, last, buildBusy = false, onMove, onOpen, onBuild, onBuildAgain }: {
		team: Team; gaps: GapStatus; connected: boolean; now: number; reorderable: boolean; first: boolean; last: boolean; buildBusy?: boolean;
		onMove: (delta: -1 | 1) => void; onOpen: () => void; onBuild: (on: boolean) => void; onBuildAgain: (m: TeamMember) => void;
	} = $props();

	const ROW_H = 330;
	let drawerOpen = $state(false);
	const slots = $derived(Array.from({ length: MAX_MEMBERS }, (_x, i) => team.members[i] ?? null));

	function open(e: MouseEvent) {
		if ((e.target as HTMLElement).closest('button, a, input, label')) return;
		onOpen();
	}
</script>

<article class="team" id="team-{team.id}" data-testid="team-{team.id}">
	<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
	<div class="row" style="--row-h: {ROW_H}px; --side-inset: {slantInset(ROW_H) + 12}px" onclick={open}>
		{#each slots as m, i (m?.id ?? `empty-${i}`)}
			<TeamRibbon member={m} {onBuildAgain} />
		{/each}
		<div class="side">
			<TeamInfo {team} {gaps} {connected} {drawerOpen} {buildBusy} {onBuild} onToggleDrawer={() => (drawerOpen = !drawerOpen)} />
			<button type="button" class="edit" onclick={onOpen} aria-label="Edit {team.name}">Edit</button>
		</div>
		<div class="arrows">
			<button type="button" onclick={() => onMove(-1)} disabled={!reorderable || first} aria-label="Move {team.name} up">▲</button>
			<button type="button" onclick={() => onMove(1)} disabled={!reorderable || last} aria-label="Move {team.name} down">▼</button>
		</div>
	</div>
	{#if drawerOpen && team.shortfall !== null}<TeamShortfall {team} {gaps} {connected} {now} />{/if}
</article>

<style>
	.team { margin-bottom: 14px; background: var(--glass-bg); border: 1px solid var(--glass-border); border-radius: 12px;
		backdrop-filter: blur(var(--glass-blur)); overflow: hidden; }
	.row { position: relative; display: grid; grid-template-columns: repeat(4, 1fr) 1.15fr; gap: 6px; height: var(--row-h);
		padding: 0 40px 0 60px; cursor: pointer; }
	.side { padding: 16px 0 16px var(--side-inset); display: flex; flex-direction: column; gap: 8px; min-width: 0; cursor: default; }
	.edit { align-self: flex-start; font-size: 12px; }
	.arrows { position: absolute; right: 8px; top: 50%; transform: translateY(-50%); display: flex; flex-direction: column; gap: 4px;
		opacity: 0; transition: opacity 0.12s; }
	.team:hover .arrows, .team:focus-within .arrows { opacity: 1; }
	.arrows button { width: 26px; height: 26px; border-radius: 50%; padding: 0; }
	/* Below this width five columns leave each ribbon too narrow for its info lines (about 165px at 1101px),
	   so the team info moves under the ribbons and the four ribbons share the full row. */
	@media (max-width: 1400px) {
		.row { grid-template-columns: repeat(4, 1fr); height: auto; padding: 0 60px; }
		.row > :global(.rib) { height: var(--row-h); }
		.side { grid-column: 1 / -1; padding: 12px 0; }
	}
</style>
