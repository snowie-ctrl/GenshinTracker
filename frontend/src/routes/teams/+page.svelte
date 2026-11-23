<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api, errorMessage } from '$lib/api';
	import { shouldPoll } from '$lib/materials';
	import { sync } from '$lib/sync.svelte';
	import TagChip from '$lib/TagChip.svelte';
	import TagManager from '$lib/TagManager.svelte';
	import TeamEditorModal from '$lib/TeamEditorModal.svelte';
	import TeamRow from '$lib/TeamRow.svelte';
	import {
		changeMessage, memberLookup, willLower,
		filterActive, filterTeams, loadTeamFilter, moveItem, pruneTeamFilter, saveTeamFilter, toggleTag, toggleUntagged,
		type TeamFilter
	} from '$lib/teams';
	import type { TagWithCount, Team, TeamMember, TeamsResponse } from '$lib/types';

	let data = $state<TeamsResponse | null>(null);
	let tags = $state<TagWithCount[]>([]);
	let error = $state<string | null>(null);
	let toast = $state<string | null>(null);
	let notice = $state<string | null>(null);
	let filter = $state<TeamFilter>(loadTeamFilter());
	let showTags = $state(false);
	let now = $state(Date.now());
	const shown = $derived(data ? filterTeams(data.teams, filter) : []);
	// Moving a team among a filtered subset would shuffle hidden teams in surprising ways.
	const canReorder = $derived(!filterActive(filter));

	$effect(() => {
		void sync.version;
		load();
	});

	onMount(() => {
		const t = setInterval(() => {
			now = Date.now();
			if (shouldPoll(data?.gaps)) load();
		}, 3000);
		return () => clearInterval(t);
	});

	async function load() {
		try {
			[data, tags] = await Promise.all([api.teams(), api.tags()]);
			const pruned = pruneTeamFilter(filter, tags.map((t) => t.id));
			if (pruned !== filter) setFilter(pruned);
			error = null;
		} catch (e) {
			error = errorMessage(e);
		}
	}

	function setFilter(f: TeamFilter) {
		filter = f;
		saveTeamFilter(f);
	}

	async function reorderTo(from: number, to: number) {
		if (!data || !canReorder) return;
		const before = data.teams;
		const teams = moveItem(before, from, to);
		if (teams === before) return;
		data = { ...data, teams };
		try {
			await api.reorderTeams(teams.map((t) => t.id));
		} catch (e) {
			data = { ...data, teams: before };
			toast = `Could not reorder: ${errorMessage(e)}`;
		}
	}

	function indexOf(id: number): number {
		return data ? data.teams.findIndex((t) => t.id === id) : -1;
	}

	const editParam = $derived(page.url.searchParams.get('edit'));
	const editId = $derived(editParam === 'new' ? null : editParam !== null && /^\d+$/.test(editParam) ? Number(editParam) : undefined);

	function openEditor(id: number | 'new') {
		void goto(`/teams?edit=${id}`, { noScroll: true, keepFocus: true });
	}

	function closeEditor() {
		void goto('/teams', { noScroll: true, keepFocus: true });
	}

	async function editorDone(message: string) {
		notice = message;
		await goto('/teams', { noScroll: true });
		await load();
	}

	async function setBuild(team: Team, on: boolean) {
		if (!data) return;
		if (!on) {
			const names = willLower(data.teams, memberLookup(data.teams), team.id, { memberIds: team.members.map((m) => m.id), hasBuild: false });
			if (names.length && !confirm(`Turn off Build? This moves ${names.join(', ')} off Build.`)) return;
		}
		const before = data.teams;
		data = { ...data, teams: data.teams.map((t) => (t.id === team.id ? { ...t, has_build_tag: on } : t)) };
		try {
			const r = await api.setTeamBuild(team.id, on);
			const msg = changeMessage('', r.raised, r.lowered);
			if (msg) notice = msg;
			await load();
		} catch (e) {
			if (data) data = { ...data, teams: before };
			toast = `Could not change Build for ${team.name}: ${errorMessage(e)}`;
		}
	}

	async function buildAgain(m: TeamMember) {
		try {
			await api.setGoal(m.id, { goal: 'build' });
			await load();
		} catch (e) {
			toast = `Could not set ${m.name} to Build: ${errorMessage(e)}`;
		}
	}
</script>

<div class="head">
	<h1>Teams</h1>
	<button type="button" class="primary" data-testid="new-team" onclick={() => openEditor('new')}>New team</button>
	<button type="button" onclick={() => (showTags = !showTags)} aria-expanded={showTags}>Manage tags</button>
</div>

<div class="filters" data-testid="tag-filter">
	<button type="button" class="chip" class:on={!filter.untagged && filter.tagIds.length === 0}
		onclick={() => setFilter({ tagIds: [], untagged: false })}>All</button>
	{#each tags as t (t.id)}
		<TagChip tag={t} on={filter.tagIds.includes(t.id)} onclick={() => setFilter(toggleTag(filter, t.id))} />
	{/each}
	<button type="button" class="chip" class:on={filter.untagged} onclick={() => setFilter(toggleUntagged(filter))}>Untagged</button>
</div>

{#if showTags}<TagManager onChange={load} />{/if}
{#if toast}<div class="toast error">{toast} <button type="button" onclick={() => (toast = null)}>Dismiss</button></div>{/if}
{#if notice}<div class="toast ok" role="status">{notice} <button type="button" onclick={() => (notice = null)}>Dismiss</button></div>{/if}
{#if error}<p class="error">{error}</p>{/if}

{#if data}
	{#if data.teams.length === 0}
		<section class="panel">
			<h2>Make your first team</h2>
			<p class="muted">Tag a team <strong>Build</strong> to add its members to the planner.</p>
			<button type="button" onclick={() => openEditor('new')}>New team</button>
		</section>
	{:else if shown.length === 0}
		<p class="muted">No team has these tags.</p>
	{:else if !canReorder}
		<p class="muted" data-testid="reorder-hint">Reordering is off while a tag filter is on. Show All to reorder teams.</p>
	{/if}
	{#each shown as team (team.id)}
		<TeamRow {team} gaps={data.gaps} connected={data.connected} {now} reorderable={canReorder}
			first={indexOf(team.id) === 0} last={indexOf(team.id) === data.teams.length - 1}
			onMove={(d) => reorderTo(indexOf(team.id), indexOf(team.id) + d)} onOpen={() => openEditor(team.id)}
			onBuild={(on) => setBuild(team, on)} onBuildAgain={buildAgain} />
	{/each}
{:else if !error}
	<p class="muted">Loading…</p>
{/if}

{#if editParam !== null && data}
	{#key editParam}
		{#if editId === undefined}
			<TeamEditorModal teamId={-1} teams={data.teams} onClose={closeEditor} onDone={editorDone} />
		{:else}
			<TeamEditorModal teamId={editId} teams={data.teams} onClose={closeEditor} onDone={editorDone} />
		{/if}
	{/key}
{/if}

<style>
	.head { display: flex; align-items: center; gap: 12px; }
	.filters { display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0 12px; align-items: center; }
	.toast { margin-bottom: 10px; }
	.ok { color: var(--accent); }
</style>
