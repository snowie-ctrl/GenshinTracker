<script lang="ts">
	import { onMount } from 'svelte';
	import { api, errorMessage } from '$lib/api';
	import Countdown from '$lib/Countdown.svelte';
	import { leftTotals, primosLine, sortEvents } from '$lib/events';
	import { imgSrc } from '$lib/img';
	import { sync } from '$lib/sync.svelte';
	import { timeAgo } from '$lib/time';
	import type { BannerHistoryPage, EventRow, EventsResponse } from '$lib/types';

	let data = $state<EventsResponse | null>(null);
	let error = $state<string | null>(null);
	let toast = $state<string | null>(null);
	let now = $state(Date.now());
	let open = $state<number | null>(null);
	let pool = $state<'character' | 'weapon' | 'chronicled'>('character');
	let q = $state('');
	let page = $state(1);
	let history = $state<BannerHistoryPage | null>(null);
	let timer: ReturnType<typeof setTimeout> | undefined;
	const left = $derived(data ? leftTotals(data.events) : { count: 0, primogems: 0 });

	$effect(() => {
		void sync.version;
		load();
	});

	$effect(() => {
		const p = pool, query = q, pg = page;
		clearTimeout(timer);
		timer = setTimeout(() => loadHistory(p, query, pg), 250);
		return () => clearTimeout(timer);
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

	let historyRequest = 0;

	async function loadHistory(p: string, query: string, pg: number) {
		const mine = ++historyRequest;
		try {
			const res = await api.bannerHistory(p, query, pg);
			if (mine === historyRequest) history = res;
		} catch (e) {
			if (mine === historyRequest) toast = `Could not load banner history: ${errorMessage(e)}`;
		}
	}

	async function toggle(ev: EventRow) {
		if (!data) return;
		const before = data.events;
		data = { ...data, events: sortEvents(before.map((r) => (r.id === ev.id ? { ...r, done: !r.done } : r))) };
		try {
			await api.setEventDone(ev.id, !ev.done);
		} catch (e) {
			data = { ...data, events: before };
			toast = `Could not save: ${errorMessage(e)}`;
		}
	}

	function rewardTitle(r: { name: string; count: number }): string {
		return r.count > 0 ? `${r.name} ×${r.count}` : r.name;
	}
</script>

<h1>Events</h1>
{#if toast}<div class="toast error">{toast} <button type="button" onclick={() => (toast = null)}>Dismiss</button></div>{/if}
{#if error}<p class="error">{error}</p>{/if}

{#if data}
	{#if data.fetched_at}
		<p class="muted">as of {timeAgo(data.fetched_at, now)}{#if data.error} · ⚠ last update failed: {data.error}{/if}</p>
	{:else}
		<p class="muted">{data.connected ? 'Sync to load the event calendar' : 'Connect HoYoLAB in Settings to load events'}{#if data.error}<br />⚠ last update failed: {data.error}{/if}</p>
	{/if}

	<section class="panel" data-testid="live-banners">
		<h2>Live banners</h2>
		<div class="banners">
			{#each data.banners.current as b (b.id)}
				<div class="banner">
					<div class="title">{b.name} <span class="muted">· {b.pool}</span></div>
					<div class="items">
						{#each b.items as it (it.id)}
							<img class="r{it.rarity}" class:big={it.rarity === 5} src={imgSrc(it.icon)} alt={it.name} title={it.name} />
						{/each}
					</div>
					<div>Ends in <Countdown at={b.end} {now} /></div>
					{#if b.pulls}<div class="muted">You pulled {b.pulls.pulls} here{#if b.pulls.fives.length} · got {b.pulls.fives.join(', ')}{/if}</div>{/if}
				</div>
			{:else}
				<p class="muted">No live banners in the calendar.</p>
			{/each}
		</div>
		{#if data.banners.upcoming.length}
			<h3>Coming up</h3>
			<ul>{#each data.banners.upcoming as b (b.id)}<li>{b.name} · starts in <Countdown at={b.start} {now} /></li>{/each}</ul>
		{/if}
	</section>

	<section class="panel" data-testid="events-left">
		<h2>Events <span class="muted">· {primosLine(left)}</span></h2>
		<ul class="events">
			{#each data.events as ev (ev.id)}
				<li class:done={ev.done} data-testid="event-{ev.id}">
					<label><input type="checkbox" checked={ev.done} onchange={() => toggle(ev)} aria-label="Done: {ev.name}" /></label>
					<button type="button" class="name" onclick={() => (open = open === ev.id ? null : ev.id)}>{ev.name}</button>
					<span class="rewards">
						{#each ev.rewards as r, i (i)}<img src={imgSrc(r.icon)} alt={r.name} title={rewardTitle(r)} />{/each}
						{#if ev.primogems}<strong>{ev.primogems} primos</strong>{/if}
					</span>
					<Countdown at={ev.end} {now} />
					{#if open === ev.id && ev.description}<p class="desc">{ev.description}</p>{/if}
				</li>
			{:else}
				<li class="muted">No current events.</li>
			{/each}
		</ul>
	</section>

	<section class="panel" data-testid="resets">
		<h2>Resets</h2>
		<div class="resets">{#each data.resets as r (r.key)}<span>{r.label}: <Countdown at={r.at} {now} /></span>{/each}</div>
	</section>
{/if}

<section class="panel" data-testid="banner-history">
	<h2>Banner history</h2>
	<div class="filters">
		{#each ['character', 'weapon', 'chronicled'] as p (p)}
			<button type="button" class="chip" class:on={pool === p} onclick={() => { pool = p as typeof pool; page = 1; }}>{p}</button>
		{/each}
		<input placeholder="Search banner or item" bind:value={q} oninput={() => (page = 1)} aria-label="Search banners" />
	</div>
	{#if history}
		<table>
			<tbody>
				{#each history.rows as b (b.key)}
					<tr>
						<td>{b.name}</td>
						<td class="muted">{b.start.slice(0, 10)} – {b.end.slice(0, 10)}</td>
						<td>{#each b.featured_5 as it (it.id)}<img class="r5" src={imgSrc(it.icon)} alt={it.name} title={it.name} />{/each}
							{#each b.featured_4 as it (it.id)}<img class="r4 small" src={imgSrc(it.icon)} alt={it.name} title={it.name} />{/each}</td>
						<td>{#if b.pulls}{b.pulls.pulls} pulls{#if b.pulls.fives.length} · {b.pulls.fives.join(', ')}{/if}{/if}</td>
					</tr>
				{:else}
					<tr><td class="muted">No banners match.</td></tr>
				{/each}
			</tbody>
		</table>
		{#if history.total > history.page_size}
			<div class="pager">
				<button type="button" disabled={page <= 1} onclick={() => (page -= 1)}>Previous</button>
				<span>Page {history.page} of {Math.ceil(history.total / history.page_size)}</span>
				<button type="button" disabled={page * history.page_size >= history.total} onclick={() => (page += 1)}>Next</button>
			</div>
		{/if}
	{/if}
</section>

<style>
	section { margin-bottom: 12px; }
	.banners { display: flex; flex-wrap: wrap; gap: 12px; }
	.banner { background: var(--panel-2); border-radius: 10px; padding: 10px; min-width: 220px; }
	.items img { width: 40px; height: 40px; border-radius: 6px; }
	.items img.big { width: 64px; height: 64px; }
	.r5 { background: var(--r5); } .r4 { background: var(--r4); }
	.events { list-style: none; padding: 0; margin: 0; }
	.events li { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; padding: 6px 0; border-bottom: 1px solid var(--line); }
	.events li.done { opacity: 0.5; }
	.name { background: none; border: none; color: var(--text); cursor: pointer; text-align: left; flex: 1; }
	.rewards { display: flex; gap: 4px; align-items: center; }
	.rewards img { width: 24px; height: 24px; }
	.desc { flex-basis: 100%; margin: 4px 0 0 30px; color: var(--muted); }
	.resets { display: flex; flex-wrap: wrap; gap: 16px; }
	td img { width: 32px; height: 32px; border-radius: 6px; }
	td img.small { width: 24px; height: 24px; }
	.filters { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
	.pager { display: flex; gap: 10px; align-items: center; margin-top: 8px; }
	.toast { margin-bottom: 8px; }
</style>
