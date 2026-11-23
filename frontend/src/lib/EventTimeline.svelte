<script lang="ts">
	import { onMount } from 'svelte';
	import { timeLeft } from './events';
	import { imgSrc } from './img';
	import { buildAxis, dayTicks, placeBars, todayOffset } from './timeline';
	import type { TimelineRow } from './types';

	let { rows, now, onopen }: { rows: TimelineRow[]; now: number; onopen: (key: string) => void } = $props();

	const DAY_PX = 34;
	const LANE_PX = 36;
	const axis = $derived(buildAxis(rows, now));
	const placed = $derived(placeBars(rows, axis));
	const ticks = $derived(dayTicks(axis));
	const lanes = $derived(Math.max(1, ...placed.map((p) => p.lane + 1)));
	const width = $derived(axis.days * DAY_PX);
	const today = $derived(todayOffset(axis, now));
	let scroller: HTMLDivElement;

	onMount(() => {
		scroller.scrollLeft = Math.max(0, today * width - scroller.clientWidth / 3);
	});

	function label(p: (typeof placed)[number]): string {
		const s = p.row.start ? new Date(p.row.start).toLocaleString() : 'already running';
		const e = p.row.end ? new Date(p.row.end).toLocaleString() : '?';
		return `${p.row.name}, ${s} to ${e}`;
	}

	function right(p: (typeof placed)[number]): string {
		if (p.row.start && Date.parse(p.row.start) > now) return `starts in ${timeLeft(p.row.start, now)}`;
		return timeLeft(p.row.end, now);
	}

	function move(e: KeyboardEvent, i: number) {
		if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
		e.preventDefault();
		const next = scroller.querySelectorAll<HTMLButtonElement>('button.bar')[i + (e.key === 'ArrowRight' ? 1 : -1)];
		next?.focus();
	}
</script>

<div class="scroller" bind:this={scroller}>
	<div class="track" style="width:{width}px">
		<div class="days" style="grid-template-columns:repeat({axis.days},{DAY_PX}px)">
			{#each ticks as t (t.ms)}<span class:month={t.monthStart}>{t.label}</span>{/each}
		</div>
		<div class="lanes" style="height:{lanes * LANE_PX}px">
			<div class="today" data-testid="today-line" style="left:{today * 100}%"><span>today</span></div>
			{#each placed as p, i (p.row.key)}
				{@const ended = !!p.row.end && Date.parse(p.row.end) <= now}
				{@const src = imgSrc(p.row.image)}
				<button type="button" class="bar" data-testid="bar-{p.row.key}" aria-label={label(p)}
					class:wish={p.row.kind === 'wish'} class:done={p.row.done} class:ended class:noart={!src}
					style="left:{p.left * 100}%;width:{p.width * 100}%;top:{p.lane * LANE_PX}px;{src ? `background-image:url('${src}')` : ''}"
					onclick={() => onopen(p.row.key)} onkeydown={(e) => move(e, i)}>
					<b>{p.row.name}</b>
					<i class:soon={p.row.ending_soon}>{right(p)}{p.clampedEnd ? ' →' : ''}</i>
				</button>
			{/each}
		</div>
	</div>
</div>

<style>
	.scroller { overflow-x: auto; padding-top: 18px; }
	.track { position: relative; }
	.days { display: grid; font-size: 10px; color: var(--muted); border-bottom: 1px solid var(--line); margin-bottom: 6px; }
	.days span { padding-left: 3px; border-left: 1px solid var(--line); }
	.days span.month { color: var(--text); font-weight: 600; }
	.lanes { position: relative; }
	.today { position: absolute; top: -26px; bottom: 0; width: 2px; background: #e8cf9c; box-shadow: 0 0 8px #e8cf9c; z-index: 3; pointer-events: none; }
	.today span { position: absolute; top: -2px; left: 5px; font-size: 10px; color: #e8cf9c; }
	.bar { position: absolute; height: 30px; border-radius: 7px; border: none; padding: 0; overflow: hidden; cursor: pointer;
		background: linear-gradient(120deg, rgba(120, 130, 180, 0.35), rgba(60, 70, 110, 0.35)) center 30% / cover;
		color: #fff; text-align: left; }
	.bar::after { content: ''; position: absolute; inset: 0; background: linear-gradient(90deg, rgba(7, 10, 20, 0.85), rgba(7, 10, 20, 0.35) 55%, rgba(7, 10, 20, 0.1)); }
	.bar b { position: absolute; left: 8px; top: 7px; z-index: 1; font-size: 12px; white-space: nowrap; text-shadow: 0 1px 2px #000; }
	.bar i { position: absolute; right: 8px; top: 8px; z-index: 1; font-style: normal; font-size: 11px; color: #e8cf9c; text-shadow: 0 1px 2px #000; }
	.bar i.soon { color: var(--warn); }
	.bar.wish { outline: 1px solid rgba(232, 207, 156, 0.6); }
	.bar.done, .bar.ended { filter: grayscale(0.85) brightness(0.6); }
	.bar:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
</style>
