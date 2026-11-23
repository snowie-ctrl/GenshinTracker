<script lang="ts">
	import { onMount } from 'svelte';
	import { beforeNavigate } from '$app/navigation';
	import { ApiError, api, errorMessage } from './api';
	import CharacterFilterBar from './CharacterFilterBar.svelte';
	import { loadCharacterView } from './characterView';
	import CharacterTile from './CharacterTile.svelte';
	import { imgSrc } from './img';
	import { emptyFilters, matches, sortCharacters, type Filters } from './status';
	import TagChip from './TagChip.svelte';
	import {
		BUILD_TAG_ID, MAX_MEMBERS, addMember, changeMessage, charLookup, moveItem, removeMember, teamErrorField,
		validateTeam, willLower, willRaise, type FieldError
	} from './teams';
	import type { Character, MemberDraft, TagWithCount, Team } from './types';

	let { teamId, teams, onClose, onDone }: {
		teamId: number | null; teams: Team[]; onClose: () => void; onDone: (message: string) => void;
	} = $props();

	let dialog: HTMLDialogElement;
	let chars = $state<Character[]>([]);
	let tags = $state<TagWithCount[]>([]);
	let name = $state('');
	let notes = $state('');
	let members = $state<MemberDraft[]>([]);
	let tagIds = $state<number[]>([]);
	let newTags = $state<string[]>([]);
	let tagInput = $state('');
	let filters = $state<Filters>(emptyFilters());
	let sort = $state(loadCharacterView().sort);
	let original = $state({ memberIds: [] as number[], hadBuild: false });
	let snapshot = $state('');
	let loading = $state(true);
	let missing = $state(false);
	let loadFailed = $state(false);
	let saving = $state(false);
	let error = $state<string | null>(null);
	let fieldError = $state<FieldError | null>(null);
	let savedName = $state('');   // the Delete confirmation names the team as saved, not as being edited
	let dragSlot = $state<number | null>(null);

	const byId = $derived(new Map(chars.map((c) => [c.id, c])));
	const hasBuild = $derived(tagIds.includes(BUILD_TAG_ID));   // a typed "build" resolves to the Build tag itself
	const raising = $derived(willRaise(chars, { members, hasBuild }, original));
	const lowering = $derived(willLower(teams, charLookup(chars), teamId, { memberIds: members.map((m) => m.character_id), hasBuild }));
	const pickable = $derived(sortCharacters(chars.filter((c) => matches(c, filters)), sort));
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

	let approved = false;   // set when our own code closes the dialog, so the close event does not ask again

	onMount(() => {
		dialog.showModal();
		load();
		return () => {
			if (dialog.open) {
				approved = true;
				dialog.close();
			}
		};
	});

	/** The one way out: close the dialog (the browser puts focus back on the button that opened it), then act. */
	function finish(action: () => void) {
		snapshot = formState();                          // so the navigation guard does not ask again
		approved = true;
		if (dialog.open) dialog.close();
		action();
	}

	function onCancel(e: Event) {
		// Chromium makes a repeated Escape (no user activation since the last one) non-cancelable;
		// then the dialog closes natively and onNativeClose asks instead, so this must not ask too.
		if (!e.cancelable) return;
		e.preventDefault();
		requestClose();
	}

	function onNativeClose() {
		if (approved) return;
		if (dirty && !saving && !confirm('Discard changes?')) {
			dialog.showModal();
			return;
		}
		finish(onClose);
	}

	beforeNavigate(({ cancel }) => {
		if (dirty && !saving && !confirm('Discard changes?')) cancel();
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

	function setBuild(on: boolean) {
		tagIds = on ? [...new Set([...tagIds, BUILD_TAG_ID])] : tagIds.filter((t) => t !== BUILD_TAG_ID);
	}

	function requestClose() {
		if (dirty && !saving && !confirm('Discard changes?')) return;
		finish(onClose);
	}

	async function save() {
		fieldError = validateTeam(name, members.length);
		if (fieldError) return;
		saving = true;
		const body = { name, notes, members, tag_ids: tagIds, new_tags: newTags };
		try {
			const res = teamId === null ? await api.createTeam(body) : await api.updateTeam(teamId, body);
			const message = changeMessage('Saved', res.raised, res.lowered);
			finish(() => onDone(message));
		} catch (e) {
			if (e instanceof ApiError && e.status === 404) {
				missing = true;
				snapshot = formState();
			}
			else if (e instanceof ApiError && e.status === 422) fieldError = { field: teamErrorField(e.message), message: e.message };
			else error = errorMessage(e);
		} finally {
			saving = false;
		}
	}

	async function remove() {
		if (teamId === null) return;
		const moving = willLower(teams, charLookup(chars), teamId, null);
		const extra = moving.length ? ` This moves ${moving.join(', ')} off Build.` : '';
		if (!confirm(`Delete "${savedName}"?${extra}`)) return;
		try {
			saving = true;
			const res = await api.deleteTeam(teamId);
			const message = changeMessage('Deleted', [], res.lowered);
			finish(() => onDone(message));
		} catch (e) {
			if (e instanceof ApiError && e.status === 404) {
				missing = true;
				snapshot = formState();
			}
			else error = errorMessage(e);
		} finally {
			saving = false;
		}
	}
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions -->
<dialog bind:this={dialog} class="modal" aria-label={teamId === null ? 'New team' : 'Edit team'}
	oncancel={onCancel} onclose={onNativeClose}
	onclick={(e) => { if (e.target === dialog) requestClose(); }}>
	{#if loading}
		<p class="muted">Loading…</p>
	{:else if missing}
		<p>This team no longer exists.</p>
		<button type="button" onclick={() => finish(onClose)}>Close</button>
	{:else if loadFailed}
		<div class="toast error">Could not load the team editor: {error} <button type="button" onclick={load}>Retry</button></div>
		<button type="button" onclick={() => finish(onClose)}>Close</button>
	{:else}
		<div class="head">
			<input class="name" bind:value={name} maxlength="60" aria-label="Team name"
				aria-invalid={fieldError?.field === 'name'} aria-describedby={fieldError?.field === 'name' ? 'err-name' : undefined} />
			<label class="sw-row"><button type="button" role="switch" aria-checked={hasBuild} aria-label="Build" class="sw" class:on={hasBuild}
				onclick={() => setBuild(!hasBuild)}></button> Build</label>
			<button type="button" class="x" onclick={requestClose} aria-label="Close">✕</button>
		</div>
		{#if fieldError?.field === 'name'}<p class="error" id="err-name" data-testid="error-name">{fieldError.message}</p>{/if}
		{#if error}<div class="toast error">{error} <button type="button" onclick={() => (error = null)}>Dismiss</button></div>{/if}

		<div class="tagrow">
			{#each tags.filter((t) => !t.builtin) as t (t.id)}<TagChip tag={t} on={tagIds.includes(t.id)} onclick={() => toggleTagId(t.id)} />{/each}
			{#each newTags as nt (nt)}
				<TagChip tag={{ id: -1, name: `${nt} (new)`, color: 'blue', builtin: false }} onclick={() => (newTags = newTags.filter((x) => x !== nt))} />
			{/each}
			<form onsubmit={addTypedTag}><input bind:value={tagInput} maxlength="30" placeholder="+ new tag" aria-label="Add tag" /></form>
			<textarea bind:value={notes} maxlength="2000" rows="2" aria-label="Notes" placeholder="Notes"
				aria-invalid={fieldError?.field === 'notes'}></textarea>
		</div>
		{#if fieldError?.field === 'tags' || fieldError?.field === 'notes'}<p class="error">{fieldError.message}</p>{/if}

		<div class="slots">
			{#each Array.from({ length: MAX_MEMBERS }) as _x, i (i)}
				{@const m = members[i]}
				{@const c = m ? byId.get(m.character_id) : undefined}
				<div class="slot" class:empty={!m} class:unowned={c && !c.owned} data-testid="slot-{i}" role="listitem" draggable={!!m}
					ondragstart={() => (dragSlot = i)} ondragend={() => (dragSlot = null)} ondragover={(e) => e.preventDefault()}
					ondrop={() => { if (dragSlot !== null && m) members = moveItem(members, dragSlot, i); dragSlot = null; }}>
					{#if m}
						<div class="art" style={c?.splash ? `background-image: url(${imgSrc(c.splash)})` : ''}></div>
						<div class="ft">
							<b>{c?.name ?? `Character ${m.character_id}`}</b>{#if c && !c.owned}<span class="muted"> Not owned</span>{/if}
							<input value={m.role} maxlength="40" placeholder="Role" aria-label="Role for {c?.name ?? m.character_id}"
								oninput={(e) => (members = members.map((x, j) => (j === i ? { ...x, role: (e.currentTarget as HTMLInputElement).value } : x)))} />
							<div class="slot-actions">
								<button type="button" disabled={i === 0} onclick={() => (members = moveItem(members, i, i - 1))} aria-label="Move left">◀</button>
								<button type="button" disabled={i === members.length - 1} onclick={() => (members = moveItem(members, i, i + 1))} aria-label="Move right">▶</button>
								<button type="button" onclick={() => (members = removeMember(members, i))} aria-label="Remove {c?.name ?? m.character_id}">✕</button>
							</div>
						</div>
					{:else}
						<span class="muted">Empty slot</span>
					{/if}
				</div>
			{/each}
		</div>
		{#if fieldError?.field === 'members'}<p class="error" data-testid="error-members">{fieldError.message}</p>{/if}
		{#if raising.length}<p class="warn">Saving raises {raising.join(', ')} to Build</p>{/if}
		{#if lowering.length}<p class="warn">Saving moves {lowering.join(', ')} off Build</p>{/if}
		{#if fieldError && fieldError.field === null}<p class="error">{fieldError.message}</p>{/if}

		<CharacterFilterBar bind:filters bind:sort />
		{#if members.length >= MAX_MEMBERS}<p class="muted">The team is full. Remove a member to add another.</p>{/if}
		<div class="grid">
			{#each pickable as c (c.id)}
				{@const inTeam = members.some((m) => m.character_id === c.id)}
				<CharacterTile character={c} picked={inTeam} disabled={inTeam || members.length >= MAX_MEMBERS}
					onpick={() => (members = addMember(members, c.id))} />
			{/each}
		</div>

		<div class="foot">
			{#if teamId !== null}<button type="button" class="danger" onclick={remove} disabled={saving}>Delete team</button>{/if}
			<span class="spacer"></span>
			<button type="button" onclick={requestClose}>Cancel</button>
			<button type="button" class="primary" onclick={save} disabled={saving}>Save</button>
		</div>
	{/if}
</dialog>

<style>
	.modal { width: 90vw; max-width: 1500px; height: 90vh; padding: 16px; border-radius: 14px; color: var(--text);
		background: rgba(22, 26, 44, 0.96); border: 1px solid var(--glass-border); overflow: auto; }
	.modal::backdrop { background: rgba(4, 6, 12, 0.7); }
	.head { display: flex; gap: 12px; align-items: center; margin-bottom: 10px; }
	.name { width: 280px; font-size: 16px; }
	.x { margin-left: auto; }
	.sw-row { display: flex; gap: 6px; align-items: center; font-size: 13px; }
	.sw { width: 32px; height: 18px; border-radius: 9px; padding: 0; border: 1px solid var(--glass-border); background: #3a3f50; position: relative; }
	.sw::after { content: ''; position: absolute; left: 2px; top: 2px; width: 12px; height: 12px; border-radius: 50%; background: var(--cream); }
	.sw.on { background: var(--gold); } .sw.on::after { left: 16px; background: #17130b; }
	.tagrow { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-bottom: 10px; }
	.tagrow textarea { flex: 1; min-width: 240px; }
	.slots { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
	.slot { border-radius: 10px; overflow: hidden; background: rgba(255, 255, 255, 0.05); min-height: 180px; }
	.slot.empty { border: 2px dashed rgba(255, 255, 255, 0.2); background: none; display: grid; place-items: center; }
	.art { height: 120px; background-size: auto 130%; background-position: center 20%; background-repeat: no-repeat; }
	.unowned .art { filter: grayscale(1) brightness(0.55); }
	.ft { padding: 6px; display: flex; flex-direction: column; gap: 4px; }
	.ft input { width: 100%; }
	.slot-actions { display: flex; gap: 4px; }
	.warn { color: var(--warn); margin: 6px 0; }
	.grid { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 4px; }
	.foot { display: flex; gap: 10px; align-items: center; margin-top: 14px; position: sticky; bottom: -16px;
		background: rgba(22, 26, 44, 0.96); padding: 10px 0; }
	.spacer { flex: 1; }
</style>
