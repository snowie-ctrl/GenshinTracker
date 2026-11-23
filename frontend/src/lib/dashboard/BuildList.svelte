<script lang="ts">
	import { api, errorMessage } from '$lib/api';
	import { moveItem } from '$lib/dashboard';
	import type { BuildCard as Card, GapStatus, PriorityResult } from '$lib/types';
	import BuildCard from './BuildCard.svelte';

	let { builds, gaps, now, onsaved }: {
		builds: Card[]; gaps: GapStatus; now: number; onsaved: (r: PriorityResult) => void;
	} = $props();
	let pending = $state<Card[] | null>(null);
	let saving = $state(false);
	let error = $state<string | null>(null);
	let dragFrom = $state<number | null>(null);
	const shown = $derived(pending ?? builds);

	async function move(from: number, to: number) {
		if (saving || from === to || to < 0 || to >= shown.length) return;
		const next = moveItem(shown, from, to);
		pending = next;
		saving = true;
		error = null;
		try {
			onsaved(await api.setPriority(next.map((c) => c.character.id)));
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
		<p class="muted">Mark characters as Build on <a href="/characters">Characters</a> to plan here.</p>
	{:else}
		<ol class="list">
			{#each shown as card, i (card.character.id)}
				<li draggable={!saving}
					ondragstart={() => (dragFrom = i)}
					ondragover={(e) => e.preventDefault()}
					ondrop={(e) => { e.preventDefault(); if (dragFrom !== null) move(dragFrom, i); dragFrom = null; }}
					ondragend={() => (dragFrom = null)}>
					<BuildCard {card} position={i + 1} {gaps} {now} disabled={saving} first={i === 0}
						last={i === shown.length - 1} onup={() => move(i, i - 1)} ondown={() => move(i, i + 1)} />
				</li>
			{/each}
		</ol>
	{/if}
</section>

<style>
	.list { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
</style>
