<script lang="ts">
	import Countdown from '$lib/Countdown.svelte';
	import { api, errorMessage } from '$lib/api';
	import { topReward } from '$lib/dashboard';
	import { imgSrc } from '$lib/img';
	import type { DashEventItem } from '$lib/types';

	let { events, fetchedAt, now }: { events: DashEventItem[]; fetchedAt: string | null; now: number } = $props();
	let overrides = $state<Record<number, boolean>>({});
	let toast = $state<string | null>(null);
	const rows = $derived(events.map((e) => (e.kind === 'event' && e.id in overrides ? { ...e, done: overrides[e.id] } : e)));

	async function toggle(id: number, done: boolean) {
		overrides = { ...overrides, [id]: done };
		try {
			await api.setEventDone(id, done);
			toast = null;
		} catch (e) {
			overrides = { ...overrides, [id]: !done };
			toast = errorMessage(e);
		}
	}
</script>

<section class="panel" data-testid="dash-events">
	<h2><a href="/events">Events</a></h2>
	{#if toast}<p class="error">{toast}</p>{/if}
	{#if !fetchedAt}<p class="muted">Sync to load events</p>{/if}
	<ul>
		{#each rows as e (e.id)}
			<li class:done={e.done} data-testid="dash-event-{e.id}">
				{#if e.kind === 'event'}
					{@const r = topReward(e.rewards)}
					<input type="checkbox" checked={e.done} disabled={e.finished} aria-label="Done: {e.name}"
						onchange={() => toggle(e.id, !e.done)} />
					{#if r && imgSrc(r.icon)}<img src={imgSrc(r.icon)} alt="" />{/if}
					<span class="name">{e.name}</span>
					<Countdown at={e.end} {now} warn={!e.done} />
				{:else}
					<span class="reset">↻</span><span class="name">{e.name}</span><Countdown at={e.end} {now} />
				{/if}
			</li>
		{/each}
	</ul>
</section>

<style>
	ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
	li { display: flex; gap: 8px; align-items: center; }
	li.done { opacity: 0.45; }
	img { width: 24px; height: 24px; }
	.name { flex: 1; }
	.reset { width: 13px; text-align: center; color: var(--muted); }
</style>
