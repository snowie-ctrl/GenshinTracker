<script lang="ts">
	import { imgSrc } from './img';

	let {
		label, on, onclick, color = 'var(--pill-neutral)', ink = '#10131f', image = null, readonly = false
	}: {
		label: string; on: boolean; onclick?: () => void; color?: string; ink?: string; image?: string | null;
		readonly?: boolean;
	} = $props();

	let broken = $state(false);
	const src = $derived(image && !broken ? imgSrc(image) : null);
</script>

{#snippet content()}
	{#if src}<img {src} alt="" width="16" height="16" onerror={() => (broken = true)} />{/if}
	{label}
{/snippet}

{#if readonly}
	<span class="pill" class:on style="--pill: {color}; --pill-ink: {ink}">{@render content()}</span>
{:else}
	<button type="button" class="pill" class:on aria-pressed={on} style="--pill: {color}; --pill-ink: {ink}" {onclick}>
		{@render content()}
	</button>
{/if}

<style>
	.pill {
		display: inline-flex; align-items: center; gap: 5px; border-radius: 999px; padding: 3px 11px; font-size: 12px;
		background: transparent; border: 1px solid var(--pill); color: var(--cream);
	}
	button.pill:hover:not(.on) { background: color-mix(in srgb, var(--pill) 18%, transparent); }
	.pill.on { background: var(--pill); color: var(--pill-ink); font-weight: 600; }
	img { display: block; }
</style>
