<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { api, errorMessage } from '$lib/api';
	import { shouldPoll } from '$lib/materials';
	import { sync } from '$lib/sync.svelte';
	import TagChip from '$lib/TagChip.svelte';
	import TagManager from '$lib/TagManager.svelte';
	import TeamCard from '$lib/TeamCard.svelte';
	import {
		filterTeams, loadTeamFilter, moveItem, saveTeamFilter, toggleTag, toggleUntagged, type TeamFilter
	} from '$lib/teams';
	import type { TagWithCount, TeamMember, TeamsResponse } from '$lib/types';

	let data = $state<TeamsResponse | null>(null);
	let tags = $state<TagWithCount[]>([]);
	let error = $state<string | null>(null);
	let toast = $state<string | null>(null);
	let saved = $state<string | null>(page.url.searchParams.get('saved'));
	let filter = $state<TeamFilter>(loadTeamFilter());
	let showTags = $state(false);
	let dragId = $state<number | null>(null);
	let now = $state(Date.now());
	const shown = $derived(data ? filterTeams(data.teams, filter) : []);

	$effect(() => {
		void sync.version;
		load();
	});

	onMount(() => {
		if (saved) history.replaceState(history.state, '', `/teams${location.hash}`);
		const t = setInterval(() => {
			now = Date.now();
			if (shouldPoll(data?.gaps)) load();
		}, 3000);
		return () => clearInterval(t);
	});

	async function load() {
		try {
			[data, tags] = await Promise.all([api.teams(), api.tags()]);
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
		if (!data) return;
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

	function drop(targetId: number) {
		if (dragId !== null && dragId !== targetId) reorderTo(indexOf(dragId), indexOf(targetId));
		dragId = null;
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
	<a class="button primary" href="/teams/new" data-testid="new-team">New team</a>
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
{#if saved}<div class="toast ok" role="status">{saved} <button type="button" onclick={() => (saved = null)}>Dismiss</button></div>{/if}
{#if error}<p class="error">{error}</p>{/if}

{#if data}
	{#if data.teams.length === 0}
		<section class="panel">
			<h2>Make your first team</h2>
			<p class="muted">Tag a team <strong>Build</strong> to add its members to the planner.</p>
			<a href="/teams/new">New team</a>
		</section>
	{:else if shown.length === 0}
		<p class="muted">No team has these tags.</p>
	{/if}
	{#each shown as team (team.id)}
		<div role="listitem" draggable="true" ondragstart={() => (dragId = team.id)} ondragend={() => (dragId = null)}
			ondragover={(e) => e.preventDefault()} ondrop={() => drop(team.id)}>
			<TeamCard {team} gaps={data.gaps} connected={data.connected} {now} onBuildAgain={buildAgain}
				onMove={(d) => reorderTo(indexOf(team.id), indexOf(team.id) + d)}
				first={indexOf(team.id) === 0} last={indexOf(team.id) === data.teams.length - 1} />
		</div>
	{/each}
{:else if !error}
	<p class="muted">Loading…</p>
{/if}

<style>
	.head { display: flex; align-items: center; gap: 12px; }
	.filters { display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0 12px; align-items: center; }
	.toast { margin-bottom: 10px; }
	.ok { color: var(--accent); }
	a.button.primary {
		background: var(--accent); color: #111; border: 1px solid var(--accent); border-radius: 6px;
		padding: 4px 10px; font-weight: 600; text-decoration: none;
	}
</style>
