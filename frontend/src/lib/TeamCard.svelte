<script lang="ts">
	import { imgSrc } from './img';
	import { gapLabel, gapsSettled } from './materials';
	import MaterialTile from './MaterialTile.svelte';
	import TagChip from './TagChip.svelte';
	import { MAX_MEMBERS, farmRows, memberLine, teamTileView, weaponLine } from './teams';
	import type { GapStatus, Team, TeamMember } from './types';

	let { team, gaps, connected, now, onBuildAgain, onMove, first, last }: {
		team: Team; gaps: GapStatus; connected: boolean; now: number; onBuildAgain: (m: TeamMember) => void;
		onMove: (delta: -1 | 1) => void; first: boolean; last: boolean;
	} = $props();

	let notesOpen = $state(false);
	const empty = $derived(Array.from({ length: MAX_MEMBERS - team.members.length }));
	const rows = $derived(farmRows(team.shortfall ?? []));
	const anyNotCalculated = $derived(team.members.some((m) => m.not_calculated));
	const pct = (v: number | null) => Math.round((v ?? 0) * 100);
</script>

<article class="team panel" id="team-{team.id}" data-testid="team-{team.id}">
	<header>
		<span class="handle" title="Drag to reorder" aria-hidden="true">⋮⋮</span>
		<h2>{team.name}</h2>
		<div class="tags">{#each team.tags as t (t.id)}<TagChip tag={t} />{/each}</div>
		<div class="actions">
			<button type="button" onclick={() => onMove(-1)} disabled={first} aria-label="Move {team.name} up">↑</button>
			<button type="button" onclick={() => onMove(1)} disabled={last} aria-label="Move {team.name} down">↓</button>
			<a href="/teams/{team.id}">Edit</a>
		</div>
	</header>

	<div class="slots">
		{#each team.members as m (m.id)}
			<div class="slot r{m.rarity} st-{m.status}">
				<a href={m.slug ? `/characters/${m.slug}` : undefined} class="face" aria-label={m.name}>
					{#if imgSrc(m.icon)}<img src={imgSrc(m.icon)} alt="" />{:else}<div class="ph">?</div>{/if}
				</a>
				<div class="name">{m.name}</div>
				<div class="badge st-{m.status}">{m.prefarming ? 'Pre-farming' : m.status}</div>
				{#if memberLine(m)}<div class="line">{memberLine(m)}</div>{/if}
				{#if m.goal === 'build' && m.progress !== null}
					<div class="bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct(m.progress)}>
						<i style="width: {pct(m.progress)}%"></i>
					</div>
				{/if}
				{#if m.weapon}
					<div class="line weapon">
						{#if imgSrc(m.weapon.icon)}<img src={imgSrc(m.weapon.icon)} alt="" />{/if}{weaponLine(m)}
					</div>
				{/if}
				{#if m.artifact_line}<div class="line muted">{m.artifact_line}</div>{/if}
				{#if m.role}<div class="role">{m.role}</div>{/if}
				{#if m.not_building}
					<div class="warn">Not building {#if m.slug !== null}<button type="button" onclick={() => onBuildAgain(m)}>Build again</button>{/if}</div>
				{/if}
				{#if m.not_calculated}<div class="muted small">Not calculated</div>{/if}
			</div>
		{/each}
		{#each empty as _e, i (i)}<div class="slot empty" aria-hidden="true"></div>{/each}
	</div>

	{#if team.notes}
		<p class="notes" class:open={notesOpen}>{team.notes}</p>
		<button type="button" class="link" onclick={() => (notesOpen = !notesOpen)}>{notesOpen ? 'Less' : 'More'}</button>
	{/if}

	{#if team.shortfall !== null}
		<section class="shortfall" data-testid="team-shortfall-{team.id}">
			<h3>To finish this team {#if team.progress !== null}<span class="muted">· {pct(team.progress)}%</span>{/if}</h3>
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
	{/if}
</article>

<style>
	.team { margin-bottom: 12px; }
	header { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
	header h2 { margin: 0; font-size: 18px; }
	.handle { cursor: grab; color: var(--muted); }
	.tags { display: flex; gap: 4px; flex-wrap: wrap; }
	.actions { margin-left: auto; display: flex; gap: 6px; align-items: center; }
	.slots { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 10px; margin-top: 10px; }
	.slot { background: var(--panel-2); border-radius: 10px; padding: 8px; font-size: 12px; min-height: 120px; }
	.slot.empty { border: 2px dashed var(--line); background: none; }
	.face img, .ph { width: 64px; height: 64px; border-radius: 8px; display: block; background: var(--r0); }
	.r5 .face img { background: var(--r5); } .r4 .face img { background: var(--r4); }
	.ph { display: grid; place-items: center; color: var(--muted); }
	.st-unobtained .face img { filter: grayscale(1); opacity: 0.5; }
	.name { font-weight: 600; margin-top: 4px; }
	.badge { font-size: 11px; color: var(--muted); text-transform: capitalize; }
	.badge.st-building { color: var(--building); }
	.line { color: var(--text); }
	.weapon { display: flex; gap: 4px; align-items: center; }
	.weapon img { width: 20px; height: 20px; }
	.role { font-style: italic; color: var(--muted); }
	.warn { color: var(--warn); }
	.bar { height: 5px; background: #444; border-radius: 3px; margin: 4px 0; }
	.bar i { display: block; height: 100%; background: var(--building); border-radius: 3px; }
	.notes { white-space: pre-wrap; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; line-clamp: 2;
		-webkit-box-orient: vertical; margin: 8px 0 0; }
	.notes.open { display: block; }
	.link { background: none; border: none; color: var(--accent); padding: 0; cursor: pointer; }
	.shortfall { margin-top: 10px; border-top: 1px solid var(--line); padding-top: 8px; }
	.shortfall h3 { margin: 0 0 6px; font-size: 14px; }
	.tiles { display: flex; flex-wrap: wrap; gap: 8px; }
	.ok { color: var(--accent); }
	.small { font-size: 11px; }
</style>
