<!-- frontend/src/lib/BarChart.svelte -->
<script lang="ts">
	import { niceMax, type Bar } from './wishes';

	let { bars, title, height = 140 }: { bars: Bar[]; title: string; height?: number } = $props();
	const W = 26;
	const GAP = 6;
	const LABEL = 18;
	const total = (b: Bar) => b.segments.reduce((a, s) => a + s.value, 0);
	const max = $derived(niceMax(Math.max(0, ...bars.map(total))));
	const width = $derived(Math.max(bars.length * (W + GAP), W));
	const summary = $derived(bars.map((b) => `${b.label}: ${total(b)}`).join(', '));
	const h = (v: number) => (max ? (v / max) * height : 0);
</script>

<figure>
	<figcaption>{title}</figcaption>
	{#if bars.length === 0}
		<p class="muted">No data yet.</p>
	{:else}
		<div class="scroll">
			<svg viewBox="0 0 {width} {height + LABEL}" {width} height={height + LABEL} role="img" aria-label="{title}: {summary}">
				{#each bars as b, i (b.label)}
					{#each b.segments as s, j (s.name)}
						{#if s.value > 0}
							<rect x={i * (W + GAP)} width={W} height={h(s.value)} fill={s.color}
								y={height - h(b.segments.slice(0, j + 1).reduce((a, t) => a + t.value, 0))}>
								<title>{b.label} · {s.name}: {s.value}</title>
							</rect>
						{/if}
					{/each}
					<text x={i * (W + GAP) + W / 2} y={height + 13} text-anchor="middle">{b.label}</text>
				{/each}
			</svg>
		</div>
	{/if}
	<p class="sr-only">{summary}</p>
</figure>

<style>
	figure { margin: 0; }
	figcaption { font-size: 12px; color: var(--muted); margin-bottom: 6px; }
	.scroll { overflow-x: auto; }
	text { font-size: 9px; fill: var(--muted); }
	.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
</style>
