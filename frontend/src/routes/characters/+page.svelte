<script lang="ts">
	import { api, errorMessage } from '$lib/api';
	import CharacterCard from '$lib/CharacterCard.svelte';
	import FilterPill from '$lib/FilterPill.svelte';
	import TagChip from '$lib/TagChip.svelte';
	import { loadCollapsed, saveCollapsed } from '$lib/collapse';
	import { RARITY_STYLE, elementStyle } from '$lib/elements';
	import {
		ELEMENTS, SECTIONS, WEAPON_TYPES, deriveStatus, emptyFilters, groupCharacters, type Filters
	} from '$lib/status';
	import { sync } from '$lib/sync.svelte';
	import { keepKnownTags } from '$lib/teams';
	import type { Character, Goal, Status, Tag } from '$lib/types';

	let chars = $state<Character[]>([]);
	let tags = $state<Tag[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let toast = $state<string | null>(null);
	let filters = $state<Filters>(emptyFilters());
	let collapsed = $state<Record<Status, boolean>>(loadCollapsed());
	const groups = $derived(groupCharacters(chars, filters));

	$effect(() => {
		void sync.version;
		load();
	});

	async function load() {
		try {
			const [c, t] = await Promise.all([api.characters(), api.tags().catch(() => null)]);
			chars = c;
			tags = t ?? [];
			// drop a selected team tag that was deleted meanwhile (only when the tag list actually loaded)
			if (t && filters.teamTags.some((id) => !t.some((x) => x.id === id))) {
				filters.teamTags = keepKnownTags(filters.teamTags, t.map((x) => x.id));
			}
			error = null;
		} catch (e) {
			error = errorMessage(e);
		} finally {
			loading = false;
		}
	}

	async function setGoal(c: Character, goal: Goal) {
		const before = chars;
		chars = chars.map((x) => (x.id === c.id ? { ...x, goal, ...deriveStatus(x.owned, goal) } : x));
		try {
			const updated = await api.setGoal(c.id, { goal });
			chars = chars.map((x) => (x.id === updated.id ? updated : x));
		} catch (e) {
			chars = before;
			toast = `Could not save the goal for ${c.name}: ${errorMessage(e)}`;
		}
	}

	function toggle<T>(list: T[], value: T): T[] {
		return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
	}

	function toggleSection(status: Status) {
		collapsed = { ...collapsed, [status]: !collapsed[status] };
		saveCollapsed(collapsed);
	}
</script>

<h1>Characters</h1>

<div class="filters">
	<input placeholder="Search name" bind:value={filters.search} aria-label="Search characters" />
	{#each ELEMENTS as el (el)}
		<FilterPill label={el} on={filters.elements.includes(el)} color={elementStyle(el).color}
			image={elementStyle(el).icon} onclick={() => (filters.elements = toggle(filters.elements, el))} />
	{/each}
	{#each WEAPON_TYPES as w (w)}
		<FilterPill label={w} on={filters.weapons.includes(w)} onclick={() => (filters.weapons = toggle(filters.weapons, w))} />
	{/each}
	{#each [5, 4] as r (r)}
		<FilterPill label="{r}★" on={filters.rarities.includes(r)} color={RARITY_STYLE[r].color} ink={RARITY_STYLE[r].ink}
			onclick={() => (filters.rarities = toggle(filters.rarities, r))} />
	{/each}
</div>

{#if tags.length}
	<div class="filters" data-testid="team-tag-filter">
		<span class="muted">Team tag</span>
		{#each tags as t (t.id)}
			<TagChip tag={t} on={filters.teamTags.includes(t.id)} onclick={() => (filters.teamTags = toggle(filters.teamTags, t.id))} />
		{/each}
	</div>
{/if}

{#if toast}
	<div class="toast error">{toast} <button type="button" onclick={() => (toast = null)}>Dismiss</button></div>
{/if}

{#if loading}
	<p class="muted">Loading…</p>
{:else if error}
	<p class="error">{error}</p>
{:else}
	{#each SECTIONS as section (section.status)}
		<section data-testid="section-{section.status}">
			<button type="button" class="section-head" onclick={() => toggleSection(section.status)}
				aria-expanded={!collapsed[section.status]}>
				<span class="dot" style="background: var(--{section.status})"></span>
				{section.label} · {groups[section.status].length}
				<span class="muted">{collapsed[section.status] ? '▸' : '▾'}</span>
			</button>
			{#if !collapsed[section.status]}
				<div class="grid">
					{#each groups[section.status] as c (c.id)}
						<CharacterCard character={c} onGoal={(g) => setGoal(c, g)} />
					{:else}
						<p class="muted">None.</p>
					{/each}
				</div>
			{/if}
		</section>
	{/each}
{/if}

<style>
	.filters { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; align-items: center; }
	.filters input { width: 180px; }
	section { margin-bottom: 18px; }
	.section-head {
		background: none; border: none; padding: 4px 0; display: flex; gap: 8px; align-items: center;
		text-transform: uppercase; letter-spacing: 0.06em; font-size: 13px; color: var(--muted);
	}
	.dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
	.grid { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 8px; }
	.toast { margin-bottom: 10px; }
</style>
