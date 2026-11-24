<!-- frontend/src/lib/LineChart.svelte -->
<script lang="ts">
	import { linePath, lineScale } from './charts';

	type Point = { date: string; total: number };
	let { points, marks }: { points: Point[]; marks: (Point & { name: string; icon: string | null })[] } = $props();
	const W = 800;
	const H = 120;
	const top = $derived(Math.max(0, ...points.map((p) => p.total)));
	const scale = $derived(points.length ? lineScale(points.map((p) => p.date), top, W, H) : null);
</script>

<figure data-testid="primogems">
	<figcaption>Primogems spent{#if points.length} · <strong>{top.toLocaleString()}</strong>{/if}</figcaption>
	{#if !scale}
		<p class="muted">No pulls yet.</p>
	{:else}
		<svg viewBox="-8 -8 {W + 16} {H + 28}" width="100%" style="max-height: 240px" role="img"
			aria-label="Primogems spent: {top.toLocaleString()} from {points[0].date} to {points[points.length - 1].date}">
			<path class="line" d={linePath(points, W, H)} />
			{#each marks as m, i (i)}
				<circle class="mark" cx={scale.x(m.date)} cy={scale.y(m.total)} r="5"><title>{m.name} · {m.date}</title></circle>
			{/each}
			<text x="0" y={H + 18}>{points[0].date}</text>
			<text x={W} y={H + 18} text-anchor="end">{points[points.length - 1].date}</text>
		</svg>
	{/if}
</figure>

<style>
	figure { margin: 0; }
	figcaption { font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); margin-bottom: 6px; }
	figcaption strong { color: var(--cream); letter-spacing: 0; }
	.line { fill: none; stroke: var(--avg-pity); stroke-width: 2; }
	.mark { fill: var(--rarity-5); stroke: var(--bg, #070a14); stroke-width: 1.5; }
	text { font-size: 11px; fill: var(--muted); }
</style>
