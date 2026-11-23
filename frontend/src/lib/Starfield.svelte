<script lang="ts">
	import { onMount } from 'svelte';
	import { LAYERS, TILE, backgroundAnimated, layerColors, makeStars, nebula, starTile } from './starfield';

	let { animated, tint = null }: { animated: boolean; tint?: string | null } = $props();

	let reducedMotion = $state(false);
	const moving = $derived(backgroundAnimated(animated, reducedMotion));
	const stars = LAYERS.map((l) => makeStars(l.seed, l.count, l.r[0], l.r[1]));
	const tiles = $derived(
		layerColors(tint).map((color, i) => ({ ...LAYERS[i], image: starTile(stars[i], color) }))
	);

	onMount(() => {
		const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
		reducedMotion = mq.matches;
		const onChange = (e: MediaQueryListEvent) => (reducedMotion = e.matches);
		mq.addEventListener('change', onChange);
		return () => mq.removeEventListener('change', onChange);
	});
</script>

<div class="starfield" class:paused={!moving} data-testid="starfield" data-animated={String(moving)}
	data-tint={tint ?? ''} aria-hidden="true" style="--tile-w: {TILE.w}px; --tile-h: {TILE.h}px">
	<div class="nebula" style="background: {nebula(tint)}"></div>
	{#each tiles as t (t.seed)}
		<div class="dust" style="background-image: {t.image}; animation-duration: {t.seconds}s"></div>
	{/each}
</div>

<style>
	.starfield { position: fixed; inset: 0; z-index: -1; overflow: hidden; pointer-events: none; background: var(--bg); }
	.nebula {
		position: absolute; inset: -20%;
	}
	.dust {
		position: absolute; top: 0; left: 0;
		width: calc(100% + var(--tile-w)); height: calc(100% + var(--tile-h));
		background-repeat: repeat;
		will-change: transform;
		animation-name: drift; animation-timing-function: linear; animation-iteration-count: infinite;
	}
	.paused .dust { animation-play-state: paused; }
	@media (prefers-reduced-motion: reduce) { .dust { animation: none; } }
	@keyframes drift {
		from { transform: translate3d(0, 0, 0); }
		to { transform: translate3d(calc(-1 * var(--tile-w)), calc(-1 * var(--tile-h)), 0); }
	}
</style>
