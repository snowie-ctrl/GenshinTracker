<script lang="ts">
	import { imgSrc } from './img';

	let {
		label, on, onclick, color = 'var(--pill-neutral)', ink = '#10131f', image = null
	}: { label: string; on: boolean; onclick: () => void; color?: string; ink?: string; image?: string | null } = $props();

	let broken = $state(false);
	const src = $derived(image && !broken ? imgSrc(image) : null);
</script>

<button type="button" class="pill" class:on aria-pressed={on} style="--pill: {color}; --pill-ink: {ink}" {onclick}>
	{#if src}<img {src} alt="" width="16" height="16" onerror={() => (broken = true)} />{/if}
	{label}
</button>

<style>
	.pill {
		display: inline-flex; align-items: center; gap: 5px; border-radius: 999px; padding: 3px 11px; font-size: 12px;
		background: transparent; border: 1px solid var(--pill); color: var(--cream);
	}
	.pill:hover:not(.on) { background: color-mix(in srgb, var(--pill) 18%, transparent); }
	.pill.on { background: var(--pill); color: var(--pill-ink); font-weight: 600; }
	img { display: block; }
</style>
