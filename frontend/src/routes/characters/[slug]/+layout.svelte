<script lang="ts">
	import { page } from '$app/state';
	import { appearance } from '$lib/appearance.svelte';
	import CharacterBanner from '$lib/CharacterBanner.svelte';
	import { CharacterPage, setCharacterPage } from '$lib/characterPage.svelte';
	import { elementHex } from '$lib/elements';
	import { sync } from '$lib/sync.svelte';

	let { children } = $props();
	const p = new CharacterPage();
	setCharacterPage(p);

	$effect(() => {
		const slug = page.params.slug ?? '';
		void sync.version;
		p.load(slug);
	});

	$effect(() => {
		const slug = page.params.slug ?? '';
		p.loadKit(slug);
	});

	const hex = $derived(elementHex(p.c?.element));
	$effect(() => {
		appearance.tint = hex;
		return () => {
			appearance.tint = null;
		};
	});
</script>

<div class="character" style={hex ? `--el: ${hex}` : undefined}>
	<a href="/characters">← Characters</a>
	{#if p.error}
		<p class="error">{p.error}</p>
	{:else if !p.c || p.c.slug !== (page.params.slug ?? '')}
		<p class="muted">Loading…</p>
	{:else}
		<CharacterBanner c={p.c} onGoal={(g) => p.saveGoal({ goal: g })} />
		{#if p.saveError}<p class="error">{p.saveError}</p>{/if}
		{@render children()}
	{/if}
</div>

<style>
	.character :global(.card) { background: var(--glass-bg); border: 1px solid var(--glass-border); border-radius: 12px;
		padding: 12px 14px; box-shadow: var(--glass-highlight); }
	.character :global(.card h2) { margin: 0 0 10px; font-size: 12px; letter-spacing: 0.08em; color: var(--el, var(--muted)); }
	.character :global(.grid) { display: grid; grid-template-columns: 1.1fr 1fr 1fr; gap: 12px; }
	.character :global(.span2) { grid-column: span 2; }
	.character :global(.slot) { border: 1px dashed var(--glass-border); border-radius: 10px; padding: 12px; color: var(--muted); }
	@media (max-width: 1100px) {
		.character :global(.grid) { grid-template-columns: 1fr; }
		.character :global(.span2) { grid-column: auto; }
	}
</style>
