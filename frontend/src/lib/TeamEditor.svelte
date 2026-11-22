<script lang="ts">
	import { onMount } from 'svelte';
	import { beforeNavigate, goto } from '$app/navigation';
	import { ApiError, api, errorMessage } from './api';
	import { imgSrc } from './img';
	import { ELEMENTS, WEAPON_TYPES, emptyFilters, matches, type Filters } from './status';
	import TagChip from './TagChip.svelte';
	import {
		BUILD_TAG_ID, MAX_MEMBERS, addMember, moveItem, raisedMessage, removeMember, teamErrorField, validateTeam,
		willRaise, type FieldError
	} from './teams';
	import type { Character, MemberDraft, TagWithCount } from './types';

	let { teamId }: { teamId: number | null } = $props();

	let chars = $state<Character[]>([]);
	let tags = $state<TagWithCount[]>([]);
	let name = $state('');
	let notes = $state('');
	let members = $state<MemberDraft[]>([]);
	let tagIds = $state<number[]>([]);
	let newTags = $state<string[]>([]);
	let tagInput = $state('');
	let filters = $state<Filters>(emptyFilters());
	let original = $state({ memberIds: [] as number[], hadBuild: false });
	let snapshot = $state('');
	let loading = $state(true);
	let missing = $state(false);
	let loadFailed = $state(false);
	let saving = $state(false);
	let error = $state<string | null>(null);
	let fieldError = $state<FieldError | null>(null);
	let savedName = $state('');   // the Delete confirmation names the team as saved, not as being edited

	const byId = $derived(new Map(chars.map((c) => [c.id, c])));
	const hasBuild = $derived(tagIds.includes(BUILD_TAG_ID));   // a typed "build" resolves to the Build tag itself
	const raising = $derived(willRaise(chars, { members, hasBuild }, original));
	const pickable = $derived(chars.filter((c) => matches(c, filters)));
	let dragSlot = $state<number | null>(null);
	const formState = () => JSON.stringify({ name, notes, members, tagIds, newTags });
	const dirty = $derived(!loading && formState() !== snapshot);

	async function load() {
		loading = true;
		loadFailed = false;
		error = null;
		try {
			const [c, t] = await Promise.all([api.characters(), api.tags()]);
			chars = c;
			tags = t;
			if (teamId !== null) {
				const { team } = await api.team(teamId);
				name = team.name;
				savedName = team.name;
				notes = team.notes;
				members = team.members.map((m) => ({ character_id: m.id, role: m.role }));
				tagIds = team.tags.map((x) => x.id);
				original = { memberIds: members.map((m) => m.character_id), hadBuild: team.has_build_tag };
			}
		} catch (e) {
			if (e instanceof ApiError && e.status === 404) missing = true;
			else {
				loadFailed = true;
				error = errorMessage(e);
			}
		} finally {
			loading = false;
			snapshot = formState();
		}
	}

	onMount(load);

	beforeNavigate(({ cancel }) => {
		if (dirty && !saving && !confirm('Leave without saving this team?')) cancel();
	});

	$effect(() => {
		const warn = (e: BeforeUnloadEvent) => {
			if (dirty) e.preventDefault();
		};
		window.addEventListener('beforeunload', warn);
		return () => window.removeEventListener('beforeunload', warn);
	});

	function toggleTagId(id: number) {
		tagIds = tagIds.includes(id) ? tagIds.filter((t) => t !== id) : [...tagIds, id];
	}

	function addTypedTag(ev: SubmitEvent) {
		ev.preventDefault();
		const typed = tagInput.trim();
		if (!typed) return;
		const existing = tags.find((t) => t.name.toLowerCase() === typed.toLowerCase());
		if (existing) {
			if (!tagIds.includes(existing.id)) tagIds = [...tagIds, existing.id];
		} else if (!newTags.some((t) => t.toLowerCase() === typed.toLowerCase())) {
			newTags = [...newTags, typed];
		}
		tagInput = '';
	}

	function toggle<T>(list: T[], value: T): T[] {
		return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
	}

	async function save() {
		fieldError = validateTeam(name, members.length);
		if (fieldError) return;
		saving = true;
		const body = { name, notes, members, tag_ids: tagIds, new_tags: newTags };
		try {
			const res = teamId === null ? await api.createTeam(body) : await api.updateTeam(teamId, body);
			const msg = res.raised.length ? `Saved · ${raisedMessage(res.raised.length)}` : 'Saved';
			snapshot = formState();
			await goto(`/teams?saved=${encodeURIComponent(msg)}#team-${res.team.id}`);
		} catch (e) {
			if (e instanceof ApiError && e.status === 404) missing = true;
			else if (e instanceof ApiError && e.status === 422) fieldError = { field: teamErrorField(e.message), message: e.message };
			else error = errorMessage(e);
		} finally {
			saving = false;
		}
	}

	async function remove() {
		if (teamId === null || !confirm(`Delete "${savedName}"? Goals are not changed.`)) return;
		try {
			saving = true;
			await api.deleteTeam(teamId);
			snapshot = formState();
			await goto('/teams');
		} catch (e) {
			if (e instanceof ApiError && e.status === 404) missing = true;
			else error = errorMessage(e);
		} finally {
			saving = false;
		}
	}
</script>

{#if loading}
	<p class="muted">Loading…</p>
{:else if missing}
	<p>This team no longer exists. <a href="/teams">Back to Teams</a></p>
{:else if loadFailed}
	<div class="toast error">Could not load the team editor: {error} <button type="button" onclick={load}>Retry</button></div>
	<p><a href="/teams">Back to Teams</a></p>
{:else}
	<h1>{teamId === null ? 'New team' : 'Edit team'}</h1>
	{#if error}<div class="toast error">{error} <button type="button" onclick={() => (error = null)}>Dismiss</button></div>{/if}

	<section class="panel form">
		<label>Team name <input bind:value={name} maxlength="60" aria-label="Team name"
			aria-invalid={fieldError?.field === 'name'} aria-describedby={fieldError?.field === 'name' ? 'err-name' : undefined} /></label>
		{#if fieldError?.field === 'name'}<p class="error" id="err-name" data-testid="error-name">{fieldError.message}</p>{/if}
		<label>Notes <textarea bind:value={notes} maxlength="2000" rows="3" aria-label="Notes"
			aria-invalid={fieldError?.field === 'notes'} aria-describedby={fieldError?.field === 'notes' ? 'err-notes' : undefined}></textarea></label>
		{#if fieldError?.field === 'notes'}<p class="error" id="err-notes">{fieldError.message}</p>{/if}

		<div class="tagrow">
			{#each tags as t (t.id)}<TagChip tag={t} on={tagIds.includes(t.id)} onclick={() => toggleTagId(t.id)} />{/each}
			{#each newTags as nt (nt)}
				<TagChip tag={{ id: -1, name: `${nt} (new)`, color: 'blue', builtin: false }}
					onclick={() => (newTags = newTags.filter((x) => x !== nt))} />
			{/each}
			<form onsubmit={addTypedTag}>
				<input bind:value={tagInput} maxlength="30" placeholder="Add or create tag" aria-label="Add tag" />
			</form>
		</div>
		{#if fieldError?.field === 'tags'}<p class="error">{fieldError.message}</p>{/if}

		<div class="slots">
			{#each Array.from({ length: MAX_MEMBERS }) as _x, i (i)}
				{@const m = members[i]}
				{@const c = m ? byId.get(m.character_id) : undefined}
				<div class="slot" class:empty={!m} data-testid="slot-{i}" role="listitem" draggable={!!m}
					ondragstart={() => (dragSlot = i)} ondragend={() => (dragSlot = null)}
					ondragover={(e) => e.preventDefault()}
					ondrop={() => { if (dragSlot !== null && m) members = moveItem(members, dragSlot, i); dragSlot = null; }}>
					{#if m}
						{#if c && imgSrc(c.icon)}<img src={imgSrc(c.icon)} alt="" />{/if}
						<div class="name">{c?.name ?? `Character ${m.character_id}`}</div>
						<input value={m.role} maxlength="40" placeholder="Role" aria-label="Role for {c?.name ?? m.character_id}"
							oninput={(e) => (members = members.map((x, j) => (j === i ? { ...x, role: (e.currentTarget as HTMLInputElement).value } : x)))} />
						<div class="slot-actions">
							<button type="button" disabled={i === 0} onclick={() => (members = moveItem(members, i, i - 1))} aria-label="Move left">←</button>
							<button type="button" disabled={i === members.length - 1} onclick={() => (members = moveItem(members, i, i + 1))} aria-label="Move right">→</button>
							<button type="button" onclick={() => (members = removeMember(members, i))} aria-label="Remove {c?.name ?? m.character_id}">×</button>
						</div>
					{:else}
						<span class="muted">Empty</span>
					{/if}
				</div>
			{/each}
		</div>
		{#if fieldError?.field === 'members'}<p class="error" data-testid="error-members">{fieldError.message}</p>{/if}
		{#if raising.length}<p class="warn">Saving raises {raising.join(', ')} to Build</p>{/if}
		{#if fieldError && fieldError.field === null}<p class="error">{fieldError.message}</p>{/if}

		<div class="buttons">
			<button type="button" class="primary" onclick={save} disabled={saving}>Save</button>
			<a href="/teams">Cancel</a>
			{#if teamId !== null}<button type="button" class="danger" onclick={remove} disabled={saving}>Delete team</button>{/if}
		</div>
	</section>

	<section class="panel">
		<h2>Add members</h2>
		<div class="filters">
			<input placeholder="Search name" bind:value={filters.search} aria-label="Search characters" />
			{#each ELEMENTS as el (el)}
				<button type="button" class="chip" class:on={filters.elements.includes(el)} onclick={() => (filters.elements = toggle(filters.elements, el))}>{el}</button>
			{/each}
			{#each WEAPON_TYPES as w (w)}
				<button type="button" class="chip" class:on={filters.weapons.includes(w)} onclick={() => (filters.weapons = toggle(filters.weapons, w))}>{w}</button>
			{/each}
			{#each [5, 4] as r (r)}
				<button type="button" class="chip" class:on={filters.rarities.includes(r)} onclick={() => (filters.rarities = toggle(filters.rarities, r))}>{r}★</button>
			{/each}
		</div>
		{#if members.length >= MAX_MEMBERS}<p class="muted">The team is full. Remove a member to add another.</p>{/if}
		<div class="grid">
			{#each pickable as c (c.id)}
				{@const inTeam = members.some((m) => m.character_id === c.id)}
				<button type="button" class="pick r{c.rarity} st-{c.status}" data-testid="pick-{c.slug}"
					disabled={inTeam || members.length >= MAX_MEMBERS} onclick={() => (members = addMember(members, c.id))}
					aria-label="Add {c.name}">
					{#if imgSrc(c.icon)}<img src={imgSrc(c.icon)} alt="" loading="lazy" />{:else}<div class="ph">?</div>{/if}
					<span>{c.name}</span>
					{#if inTeam}<span class="muted small">In team</span>{/if}
				</button>
			{/each}
		</div>
	</section>
{/if}

<style>
	.form label { display: flex; flex-direction: column; gap: 4px; margin-bottom: 8px; }
	.tagrow { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-bottom: 10px; }
	.slots { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 10px; }
	.slot { background: var(--panel-2); border-radius: 10px; padding: 8px; min-height: 110px; }
	.slot.empty { border: 2px dashed var(--line); background: none; display: grid; place-items: center; }
	.slot img { width: 56px; height: 56px; border-radius: 8px; }
	.slot input { width: 100%; }
	.slot-actions { display: flex; gap: 4px; margin-top: 4px; }
	.buttons { display: flex; gap: 10px; align-items: center; margin-top: 10px; }
	.danger { margin-left: auto; }
	.warn { color: var(--warn); }
	.filters { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
	.grid { display: flex; flex-wrap: wrap; gap: 8px; }
	.pick { width: 96px; display: flex; flex-direction: column; align-items: center; gap: 2px; padding: 4px;
		background: var(--panel-2); border: none; border-radius: 10px; color: var(--text); cursor: pointer; font-size: 12px; }
	.pick:disabled { opacity: 0.5; cursor: default; }
	.pick img, .pick .ph { width: 80px; height: 80px; border-radius: 8px; background: var(--r0); }
	.pick.r5 img { background: var(--r5); } .pick.r4 img { background: var(--r4); }
	.pick.st-unobtained img { filter: grayscale(1); opacity: 0.6; }
	.small { font-size: 11px; }
</style>
