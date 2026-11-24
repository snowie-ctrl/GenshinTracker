<!-- frontend/src/lib/ShowcaseEditor.svelte -->
<script lang="ts">
	import { onMount } from 'svelte';
	import { imgSrc } from './img';
	import { SHOWCASE_MAX, moveId, toggleId } from './profile';
	import type { OwnedOption } from './types';

	let { owned, initial, onsave, onclose }: {
		owned: OwnedOption[]; initial: number[]; onsave: (ids: number[]) => Promise<void>; onclose: () => void;
	} = $props();
	// Seeded once from the saved selection; the editor owns its draft after opening.
	// svelte-ignore state_referenced_locally
	let ids = $state<number[]>([...initial]);
	let busy = $state(false);
	let dialog: HTMLDialogElement;
	const byId = $derived(new Map(owned.map((o) => [o.id, o])));

	onMount(() => dialog.showModal());

	async function save(next: number[]) {
		busy = true;
		try {
			await onsave(next);
		} finally {
			busy = false;
		}
	}
</script>

<dialog bind:this={dialog} {onclose} aria-labelledby="showcase-editor-title" data-testid="showcase-editor">
	<h2 id="showcase-editor-title">Edit showcase</h2>
	<p class="muted small">Pick up to {SHOWCASE_MAX} characters ({ids.length}/{SHOWCASE_MAX}). The order here is the order on the page.</p>
	<ol class="chosen">
		{#each ids as id, i (id)}
			{@const name = byId.get(id)?.name ?? String(id)}
			<li>
				<span>{name}</span>
				<button type="button" aria-label="Move {name} up" disabled={i === 0} onclick={() => (ids = moveId(ids, i, -1))}>↑</button>
				<button type="button" aria-label="Move {name} down" disabled={i === ids.length - 1} onclick={() => (ids = moveId(ids, i, 1))}>↓</button>
				<button type="button" aria-label="Remove {name}" onclick={() => (ids = toggleId(ids, id))}>×</button>
			</li>
		{/each}
	</ol>
	<div class="pick">
		{#each owned as o (o.id)}
			<button type="button" class="opt" aria-pressed={ids.includes(o.id)}
				disabled={!ids.includes(o.id) && ids.length >= SHOWCASE_MAX} onclick={() => (ids = toggleId(ids, o.id))}>
				{#if imgSrc(o.icon)}<img src={imgSrc(o.icon)} alt="" />{/if}{o.name}
			</button>
		{/each}
	</div>
	<div class="actions">
		<button type="button" onclick={() => (ids = [])}>Clear</button>
		<button type="button" onclick={() => save([])} disabled={busy}>Reset to automatic</button>
		<span class="spacer"></span>
		<button type="button" onclick={() => dialog.close()}>Cancel</button>
		<button type="button" class="primary" onclick={() => save(ids)} disabled={busy || ids.length === 0}>Save</button>
	</div>
</dialog>

<style>
	dialog { max-width: 720px; width: 92vw; }
	.chosen { display: grid; gap: 4px; padding-left: 20px; }
	.chosen li span { display: inline-block; min-width: 160px; }
	.pick { display: flex; flex-wrap: wrap; gap: 6px; margin: 10px 0; max-height: 300px; overflow: auto; }
	.opt { display: inline-flex; align-items: center; gap: 6px; }
	.opt[aria-pressed='true'] { border-color: var(--avg-pity); color: var(--avg-pity); }
	.opt img { width: 22px; height: 22px; border-radius: 50%; }
	.actions { display: flex; gap: 8px; align-items: center; }
	.spacer { flex: 1; }
	.small { font-size: 12px; }
</style>
