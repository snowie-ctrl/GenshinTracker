<!-- frontend/src/lib/Histogram.svelte -->
<script lang="ts">
	import { pityX } from './charts';
	import { niceMax } from './wishes';

	let { buckets, soft, avg }: { buckets: { bucket: string; count: number }[]; soft: number | null; avg: number | null } = $props();
	const W = 270;
	const H = 110;
	const LABEL = 16;
	const max = $derived(niceMax(Math.max(0, ...buckets.map((b) => b.count))));
	const bw = $derived(W / Math.max(1, buckets.length));
	const h = (n: number) => (max ? (n / max) * H : 0);
	const summary = $derived(buckets.map((b) => `${b.bucket}: ${b.count}`).join(', '));
</script>

<figure data-testid="pity-hist">
	<figcaption>Where your 5★s landed</figcaption>
	{#if buckets.every((b) => b.count === 0)}
		<p class="muted">No 5★ yet.</p>
	{:else}
		<svg viewBox="0 0 {W} {H + LABEL}" width="100%" role="img" aria-label="5★ pity: {summary}">
			{#each buckets as b, i (b.bucket)}
				{#if b.count > 0}
					<rect class="bar" x={i * bw + 2} width={bw - 4} y={H - h(b.count)} height={h(b.count)}>
						<title>{b.bucket}: {b.count}</title>
					</rect>
				{/if}
				<text x={i * bw + bw / 2} y={H + 12} text-anchor="middle">{b.bucket}</text>
			{/each}
			{#if soft !== null}
				<line class="soft" x1={pityX(soft, W)} x2={pityX(soft, W)} y1="0" y2={H}><title>Soft pity from {soft}</title></line>
			{/if}
			{#if avg !== null}
				<line class="avg" x1={pityX(avg, W)} x2={pityX(avg, W)} y1="0" y2={H}><title>Your average 5★ pity: {avg}</title></line>
			{/if}
		</svg>
	{/if}
</figure>

<style>
	figure { margin: 0; }
	figcaption { font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); margin-bottom: 6px; }
	.bar { fill: var(--rarity-5); }
	.soft { stroke: var(--warn); stroke-width: 2; }
	.avg { stroke: var(--avg-pity); stroke-width: 2; }
	text { font-size: 8px; fill: var(--muted); }
</style>
