<!-- frontend/src/lib/RadarChart.svelte -->
<script lang="ts">
	import { axisPoint, radarPoints } from './charts';
	import { imgSrc } from './img';

	type Series = { name: string; values: number[]; color: string };
	let { title, axes, series, size = 200, testid }: {
		title: string; axes: { label: string; icon?: string | null }[]; series: Series[]; size?: number; testid?: string;
	} = $props();

	const c = $derived(size / 2);
	const R = $derived(size / 2 - 26);
	const max = $derived(Math.max(1, ...series.flatMap((s) => s.values)));
	const summary = $derived(
		series.map((s) => `${s.name}: ${axes.map((a, i) => `${a.label} ${s.values[i] ?? 0}`).join(', ')}`).join('; ')
	);
</script>

<figure data-testid={testid}>
	<figcaption>{title}</figcaption>
	<svg viewBox="0 0 {size} {size}" width="100%" style="max-width: {size}px" role="img" aria-label="{title}: {summary}">
		{#each [0.25, 0.5, 0.75, 1] as k (k)}
			<polygon class="ring" points={radarPoints(axes.map(() => k), 1, R, c, c)} />
		{/each}
		{#each axes as a, i (a.label)}
			{@const end = axisPoint(i, axes.length, R, c, c)}
			{@const at = axisPoint(i, axes.length, R + 14, c, c)}
			<line class="spoke" x1={c} y1={c} x2={end.x} y2={end.y} />
			{#if a.icon && imgSrc(a.icon)}
				<image href={imgSrc(a.icon)} x={at.x - 8} y={at.y - 8} width="16" height="16"><title>{a.label}</title></image>
			{:else}
				<text x={at.x} y={at.y + 3} text-anchor="middle">{a.label}</text>
			{/if}
		{/each}
		{#each series as s (s.name)}
			<polygon points={radarPoints(s.values, max, R, c, c)} fill={s.color} fill-opacity="0.3" stroke={s.color}
				stroke-width="1.5"><title>{s.name}</title></polygon>
		{/each}
	</svg>
	{#if series.length > 1}
		<div class="legend">
			{#each series as s (s.name)}<span><i style="background: {s.color}"></i>{s.name}</span>{/each}
		</div>
	{/if}
</figure>

<style>
	figure { margin: 0; display: flex; flex-direction: column; align-items: center; }
	figcaption { align-self: flex-start; font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); margin-bottom: 6px; }
	.ring { fill: none; stroke: var(--line); }
	.spoke { stroke: var(--line); }
	text { font-size: 9px; fill: var(--muted); }
	.legend { display: flex; gap: 12px; font-size: 11px; color: var(--muted); }
	.legend i { display: inline-block; width: 8px; height: 8px; border-radius: 2px; margin-right: 4px; }
</style>
