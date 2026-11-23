<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { afterNavigate } from '$app/navigation';
	import { page } from '$app/state';
	import { appearance } from '$lib/appearance.svelte';
	import { isFluid, isWide } from '$lib/nav';
	import Sidebar from '$lib/Sidebar.svelte';
	import Starfield from '$lib/Starfield.svelte';
	import { sync } from '$lib/sync.svelte';

	let { children } = $props();
	const fluid = $derived(isFluid(page.url.pathname));
	const wide = $derived(isWide(page.url.pathname));

	onMount(() => {
		sync.loadConnection();
		appearance.load();
	});

	// "Sync on page load": every navigation asks for an auto sync; the backend decides if it is due.
	afterNavigate(() => {
		sync.start('auto');
	});
</script>

<Starfield animated={appearance.backgroundAnimated} />
<Sidebar />

<div class="content" class:fluid>
	{#if sync.connection?.status === 'expired'}
		<div class="banner warn">Your HoYoLAB login expired. <a href="/settings">Reconnect HoYoLAB</a></div>
	{:else if sync.connection?.status === 'missing'}
		<div class="banner">Not connected to HoYoLAB yet. <a href="/settings">Connect HoYoLAB</a></div>
	{/if}
	<main class:fluid class:wide>{@render children()}</main>
</div>

<style>
	.content { margin-left: var(--sidebar-w); min-height: 100vh; display: flex; flex-direction: column; }
	.content.fluid { height: 100vh; }
	main { flex: 1; width: 100%; max-width: 1600px; margin: 0 auto; padding: var(--gutter); }
	main.wide { max-width: none; }
	main.fluid { max-width: none; min-height: 0; display: flex; flex-direction: column; }
	.banner {
		margin: 12px var(--gutter) 0; padding: 8px 14px; border-radius: 10px;
		background: var(--glass-bg); border: 1px solid var(--glass-border);
	}
	.banner.warn { background: rgba(90, 60, 20, 0.6); border-color: rgba(240, 160, 75, 0.4); }
</style>
