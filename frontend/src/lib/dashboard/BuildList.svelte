<script lang="ts">
	import { tick } from 'svelte';
	import { api, errorMessage } from '$lib/api';
	import { moveItem } from '$lib/dashboard';
	import type { BuildCard as Card, GapStatus, PriorityResult } from '$lib/types';
	import BuildCard from './BuildCard.svelte';

	let { builds, completedCount, gaps, now, onsaved }: {
		builds: Card[]; completedCount: number; gaps: GapStatus; now: number; onsaved: (r: PriorityResult) => void;
	} = $props();
	let pending = $state<Card[] | null>(null);
	let saving = $state(false);
	let error = $state<string | null>(null);
	let announce = $state('');
	let listEl = $state<HTMLOListElement | null>(null);
	let dragFrom = $state<number | null>(null);
	const shown = $derived(pending ?? builds);

	async function move(from: number, to: number) {
		if (saving || from === to || to < 0 || to >= shown.length) return;
		const next = moveItem(shown, from, to);
		const moved = shown[from].character;
		pending = next;
		saving = true;
		error = null;
		try {
			onsaved(await api.setPriority(next.map((c) => c.character.id)));
			announce = `${moved.name} moved to P${to + 1}`;
			await tick();
			const el = listEl?.querySelector<HTMLElement>(`[data-testid="build-card-${moved.slug}"]`);
			const want = to > from ? (to < next.length - 1 ? 'down' : 'up') : to > 0 ? 'up' : 'down';
			el?.querySelector<HTMLElement>(`button[data-move="${want}"]`)?.focus();
		} catch (e) {
			error = errorMessage(e);
		} finally {
			pending = null;
			saving = false;
		}
	}
</script>

<section class="panel" data-testid="builds">
	<h2>Building</h2>
	{#if error}<p class="error" role="alert">{error}</p>{/if}
	{#if shown.length === 0}
		{#if completedCount > 0}
			<p class="muted">Every Build character is complete.</p>
		{:else}
			<p class="muted">Mark characters as Build on <a href="/characters">Characters</a> to plan here.</p>
		{/if}
	{:else}
		<ol class="list" bind:this={listEl}>
			{#each shown as card, i (card.character.id)}
				<li draggable={!saving}
					ondragstart={(e) => {
						dragFrom = i;
						if (e.dataTransfer) { e.dataTransfer.setData('text/plain', String(i)); e.dataTransfer.effectAllowed = 'move'; }
					}}
					ondragover={(e) => e.preventDefault()}
					ondrop={(e) => { e.preventDefault(); if (dragFrom !== null) move(dragFrom, i); dragFrom = null; }}
					ondragend={() => (dragFrom = null)}>
					<BuildCard {card} position={i + 1} {gaps} {now} disabled={saving} first={i === 0}
						last={i === shown.length - 1} onup={() => move(i, i - 1)} ondown={() => move(i, i + 1)} />
				</li>
			{/each}
		</ol>
	{/if}
	<p class="sr-only" aria-live="polite">{announce}</p>
</section>

<style>
	.sr-only { position: absolute; width: 1px; height: 1px; margin: -1px; padding: 0; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0; }
	.list { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
</style>
