<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { afterNavigate } from '$app/navigation';
	import { page } from '$app/state';
	import { sync } from '$lib/sync.svelte';
	import { failedParts, lastFinished, syncLabel } from '$lib/syncLabel';

	let { children } = $props();

	const NAV: { label: string; href?: string; phase?: number }[] = [
		{ label: 'Dashboard', href: '/' },
		{ label: 'Characters', href: '/characters' },
		{ label: 'Teams', phase: 4 },
		{ label: 'Inventory', href: '/inventory' },
		{ label: 'Events', phase: 5 },
		{ label: 'Map', phase: 5 },
		{ label: 'Wishes', phase: 3 },
		{ label: 'Profile', phase: 5 },
		{ label: 'Settings', href: '/settings' }
	];

	let now = $state(Date.now());
	let showDetails = $state(false);
	const last = $derived(lastFinished(sync.status));
	const failed = $derived(last ? failedParts(last) : []);

	function isActive(href: string): boolean {
		return href === '/' ? page.url.pathname === '/' : page.url.pathname.startsWith(href);
	}

	onMount(() => {
		sync.loadConnection();
		const t = setInterval(() => (now = Date.now()), 30_000);
		return () => clearInterval(t);
	});

	// "Sync on page load": every navigation asks for an auto sync; the backend decides if it's due.
	afterNavigate(() => {
		sync.start('auto');
	});
</script>

<nav class="topnav">
	<span class="brand">GenshinTracker</span>
	{#each NAV as item (item.label)}
		{#if item.href}
			<a href={item.href} class:active={isActive(item.href)}>{item.label}</a>
		{:else}
			<span class="disabled" title="Coming in phase {item.phase}">{item.label}</span>
		{/if}
	{/each}
	<div class="sync">
		<button
			type="button"
			class="label"
			class:warn={failed.length > 0}
			data-testid="sync-label"
			onclick={() => (showDetails = !showDetails)}
		>
			{syncLabel(sync.status, now)}
		</button>
		<button
			type="button"
			onclick={() => sync.start('manual')}
			disabled={sync.status?.running || sync.connection?.status !== 'connected'}
		>
			Sync
		</button>
		{#if showDetails && last}
			<div class="popover panel">
				<div class="muted">Last sync ({last.trigger})</div>
				{#each Object.entries(last.parts) as [name, part] (name)}
					<div>
						<b>{name}</b>:
						{#if part.ok}ok{#if part.count !== undefined} ({part.count}){/if}{:else}<span class="error"
								>{part.error}</span
							>{/if}
					</div>
				{/each}
			</div>
		{/if}
		{#if sync.error}<div class="sync-error error" title={sync.error}>{sync.error}</div>{/if}
	</div>
</nav>

{#if sync.connection?.status === 'expired'}
	<div class="banner warn">Your HoYoLAB login expired. <a href="/settings">Reconnect HoYoLAB</a></div>
{:else if sync.connection?.status === 'missing'}
	<div class="banner">Not connected to HoYoLAB yet. <a href="/settings">Connect HoYoLAB</a></div>
{/if}

<main>{@render children()}</main>

<style>
	.topnav {
		display: flex; align-items: center; gap: 14px; padding: 10px 16px;
		background: #101016; border-bottom: 1px solid var(--line); flex-wrap: wrap;
	}
	.brand { font-weight: 700; margin-right: 8px; }
	.topnav a { color: var(--text); text-decoration: none; padding-bottom: 2px; }
	.topnav a.active { border-bottom: 2px solid var(--accent); }
	.disabled { color: var(--unobtained); cursor: default; }
	.sync { margin-left: auto; display: flex; gap: 8px; align-items: center; position: relative; }
	.label { background: none; border: none; color: var(--muted); font-size: 12px; }
	.label.warn { color: var(--warn); }
	.popover { position: absolute; top: 34px; right: 0; z-index: 10; min-width: 260px; font-size: 12px; }
	.sync-error { position: absolute; top: 34px; right: 0; font-size: 12px; white-space: nowrap; }
	.banner { padding: 8px 16px; background: var(--panel-2); border-bottom: 1px solid var(--line); }
	.banner.warn { background: #3a2a14; }
</style>
