<script lang="ts">
	import { onMount } from 'svelte';
	import Countdown from './Countdown.svelte';
	import { imgSrc } from './img';
	import type { TimelineRow } from './types';

	let { row, now, onclose, ontoggle }: {
		row: TimelineRow; now: number; onclose: () => void; ontoggle: (row: TimelineRow) => void;
	} = $props();
	let dialog: HTMLDialogElement;
	const hero = $derived(imgSrc(row.image));
	const fmt = (s: string | null) =>
		s ? new Date(s).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '…';

	onMount(() => dialog.showModal());
</script>

<dialog bind:this={dialog} class="modal" data-testid="event-modal" aria-label={row.name}
	onclose={onclose} onclick={(e) => { if (e.target === dialog) dialog.close(); }}>
	<div class="hero" class:noart={!hero} style={hero ? `background-image:url('${hero}')` : ''}>
		<button type="button" class="x" aria-label="Close" onclick={() => dialog.close()}>✕</button>
		<h3>{row.name}</h3>
	</div>
	<div class="body">
		<div class="pills">
			<span class="pill">{fmt(row.start)} → {fmt(row.end)}</span>
			<span class="pill">{#if row.start && Date.parse(row.start) > now}starts in <Countdown at={row.start} {now} />{:else}<Countdown at={row.end} {now} warn={!row.done} />{/if}</span>
			{#if row.primogems > 0}<span class="pill">{row.primogems} primos</span>{/if}
		</div>
		{#if row.rewards.length}
			<h4>Rewards</h4>
			<div class="rewards">
				{#each row.rewards as r, i (i)}
					<div class="reward">{#if imgSrc(r.icon)}<img src={imgSrc(r.icon)} alt={r.name} title={r.name} />{/if}<span>{r.count || ''}</span></div>
				{/each}
			</div>
		{/if}
		{#if row.items}
			<h4>Featured</h4>
			<div class="featured">
				{#each row.items.featured_5 as it (it.id)}{#if imgSrc(it.icon)}<img class="r5" src={imgSrc(it.icon)} alt={it.name} title={it.name} />{/if}{/each}
				{#each row.items.featured_4 as it (it.id)}{#if imgSrc(it.icon)}<img class="r4 small" src={imgSrc(it.icon)} alt={it.name} title={it.name} />{/if}{/each}
			</div>
			{#if row.pulls}<p class="muted">You pulled {row.pulls.pulls} here{#if row.pulls.fives.length} · got {row.pulls.fives.join(', ')}{/if}</p>{/if}
		{/if}
		{#if row.description}
			<h4>About</h4>
			<div class="desc">{#each row.description.split('\n\n') as p, i (i)}<p>{p}</p>{/each}</div>
		{/if}
		{#if row.kind === 'event' && row.calendar_id !== null}
			<div class="foot">
				{#if row.finished}
					<button type="button" disabled>Completed in game</button>
				{:else}
					<button type="button" class="primary" onclick={() => ontoggle(row)}>{row.done ? 'Undo' : 'Mark done'}</button>
				{/if}
			</div>
		{/if}
	</div>
</dialog>

<style>
	.modal { width: min(460px, calc(100vw - 32px)); padding: 0; border: 1px solid var(--line); border-radius: 14px; overflow: hidden;
		background: var(--glass-bg-strong); backdrop-filter: blur(var(--glass-blur)); color: var(--text); }
	.modal::backdrop { background: rgba(0, 0, 0, 0.55); }
	.hero { position: relative; height: 150px; background: linear-gradient(120deg, rgba(120, 130, 180, 0.4), rgba(60, 70, 110, 0.4)) center / cover; }
	.hero::after { content: ''; position: absolute; inset: 0; background: linear-gradient(180deg, transparent 40%, var(--glass-bg-strong)); }
	.hero h3 { position: absolute; left: 14px; bottom: 8px; margin: 0; z-index: 1; font-size: 18px; text-shadow: 0 1px 3px #000; }
	.x { position: absolute; right: 10px; top: 8px; z-index: 2; width: 28px; height: 28px; border-radius: 50%; border: none; background: rgba(0, 0, 0, 0.5); color: #fff; cursor: pointer; }
	.body { padding: 12px 14px 14px; max-height: 60vh; overflow-y: auto; }
	.pills { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 8px; }
	.pill { padding: 2px 10px; border-radius: 999px; background: rgba(255, 255, 255, 0.08); font-size: 12px; }
	h4 { margin: 10px 0 6px; font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); }
	.rewards, .featured { display: flex; flex-wrap: wrap; gap: 6px; }
	.reward { width: 42px; text-align: center; font-size: 11px; }
	.reward img, .featured img { width: 40px; height: 40px; border-radius: 6px; }
	.featured img.small { width: 28px; height: 28px; }
	.r5 { background: var(--r5); } .r4 { background: var(--r4); }
	.desc p { margin: 0 0 8px; line-height: 1.5; color: var(--muted); }
	.foot { margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--line); }
</style>
