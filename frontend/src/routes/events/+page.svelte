<script lang="ts">
	import { onMount } from 'svelte';
	import { api, errorMessage } from '$lib/api';
	import Countdown from '$lib/Countdown.svelte';
	import EventModal from '$lib/EventModal.svelte';
	import EventTimeline from '$lib/EventTimeline.svelte';
	import { leftTotals, primosLine, setDone } from '$lib/events';
	import { imgSrc } from '$lib/img';
	import { sync } from '$lib/sync.svelte';
	import { timeAgo } from '$lib/time';
	import type { EventRow, EventsResponse, TimelineRow } from '$lib/types';

	let data = $state<EventsResponse | null>(null);
	let error = $state<string | null>(null);
	let toast = $state<string | null>(null);
	let now = $state(Date.now());
	let openKey = $state<string | null>(null);
	const left = $derived(data ? leftTotals(data.events) : { count: 0, primogems: 0 });
	const openRow = $derived(data?.timeline.find((r) => r.key === openKey) ?? null);

	$effect(() => {
		void sync.version;
		load();
	});

	onMount(() => {
		const t = setInterval(() => (now = Date.now()), 30_000);
		return () => clearInterval(t);
	});

	async function load() {
		try {
			data = await api.events();
			error = null;
		} catch (e) {
			error = errorMessage(e);
		}
	}

	/** Done lives on calendar ids; keep the checklist and every timeline row of that id in step. */
	function applyDone(id: number, done: boolean) {
		if (!data) return;
		data = {
			...data,
			events: setDone(data.events, id, done),
			timeline: data.timeline.map((r) => (r.calendar_id === id && !r.finished ? { ...r, done } : r))
		};
	}

	async function toggle(id: number, done: boolean) {
		applyDone(id, done);
		try {
			await api.setEventDone(id, done);
		} catch (e) {
			applyDone(id, !done);
			toast = `Could not save: ${errorMessage(e)}`;
		}
	}

	const toggleRow = (r: TimelineRow) => r.calendar_id !== null && toggle(r.calendar_id, !r.done);
	const toggleEvent = (ev: EventRow) => toggle(ev.id, !ev.done);
</script>

<h1>Events</h1>
{#if toast}<div class="toast error">{toast} <button type="button" onclick={() => (toast = null)}>Dismiss</button></div>{/if}
{#if error}<p class="error">{error}</p>{/if}

{#if data}
	{#if data.fetched_at}
		<p class="muted">as of {timeAgo(data.fetched_at, now)}{#if data.error} · ⚠ last update failed: {data.error}{/if}{#if data.announcements_error} · ⚠ event art update failed: {data.announcements_error}{/if}</p>
	{:else}
		<p class="muted">{data.connected ? 'Sync to load the event calendar' : 'Connect HoYoLAB in Settings to load events'}{#if data.error}<br />⚠ last update failed: {data.error}{/if}</p>
	{/if}

	<div class="top">
		<section class="panel" data-testid="timeline">
			<h2>Timeline</h2>
			{#if data.timeline.length}
				<EventTimeline rows={data.timeline} {now} onopen={(k) => (openKey = k)} />
			{:else}
				<p class="muted">No events yet.</p>
			{/if}
		</section>
		<section class="panel timers" data-testid="timers">
			<h2>Timers</h2>
			{#each data.resets as r (r.key)}<div class="t"><span>{r.label}</span><Countdown at={r.at} {now} /></div>{/each}
			{#if data.ending_soon.length}
				<h3>Ending soon</h3>
				<div data-testid="ending-soon">
					{#each data.ending_soon as e (e.key)}
						<button type="button" class="t link" onclick={() => (openKey = e.key)}><span>{e.name}</span><Countdown at={e.end} {now} warn /></button>
					{/each}
				</div>
			{/if}
		</section>
	</div>

	<section class="panel" data-testid="events-left">
		<h2>Done <span class="muted">· {primosLine(left)}</span></h2>
		<ul class="events">
			{#each data.events as ev (ev.id)}
				<li class:done={ev.done} data-testid="event-{ev.id}">
					<label title={ev.finished ? 'Completed in game' : undefined}><input type="checkbox" checked={ev.done} disabled={ev.finished} onchange={() => toggleEvent(ev)} aria-label="Done: {ev.name}" /></label>
					<span class="name">{ev.name}</span>
					{#if ev.finished}<span class="auto">auto</span>{/if}
					<span class="rewards">
						{#each ev.rewards as r, i (i)}{#if imgSrc(r.icon)}<img src={imgSrc(r.icon)} alt={r.name} title={r.count > 0 ? `${r.name} ×${r.count}` : r.name} />{/if}{/each}
						{#if ev.primogems}<strong>{ev.primogems} primos</strong>{/if}
					</span>
					<Countdown at={ev.end} {now} warn={!ev.done} />
				</li>
			{:else}
				<li class="muted">No current events.</li>
			{/each}
		</ul>
	</section>
{/if}

<section class="panel" data-testid="banner-history"></section>

{#if openRow}
	<EventModal row={openRow} {now} onclose={() => (openKey = null)} ontoggle={toggleRow} />
{/if}

<style>
	section { margin-bottom: 12px; }
	.top { display: grid; grid-template-columns: minmax(0, 1fr) 240px; gap: 12px; }
	@media (max-width: 1100px) { .top { grid-template-columns: minmax(0, 1fr); } }
	.timers .t { display: flex; justify-content: space-between; gap: 8px; padding: 5px 0; border-bottom: 1px solid var(--line); width: 100%; }
	.timers h3 { margin: 12px 0 4px; font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); }
	.link { background: none; border: none; color: var(--text); cursor: pointer; text-align: left; font: inherit; }
	.events { list-style: none; padding: 0; margin: 0; }
	.events li { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; padding: 6px 0; border-bottom: 1px solid var(--line); }
	.events li.done { opacity: 0.5; }
	.name { flex: 1; }
	.auto { font-size: 10px; padding: 1px 6px; border-radius: 999px; background: var(--panel-2); }
	.rewards { display: flex; gap: 4px; align-items: center; }
	.rewards img { width: 24px; height: 24px; }
	.toast { margin-bottom: 8px; }
</style>
