<script lang="ts">
	import { page } from '$app/state';
	import Icon from './Icon.svelte';
	import SyncItem from './SyncItem.svelte';
	import { BOTTOM_NAV, MAIN_NAV, isActive, type NavItem } from './nav';
</script>

{#snippet link(item: NavItem)}
	{@const active = isActive(item.href, page.url.pathname)}
	<a href={item.href} class="item" class:active aria-current={active ? 'page' : undefined}>
		<Icon name={item.icon} />
		<span>{item.label}</span>
	</a>
{/snippet}

<nav class="sidebar" aria-label="Main">
	<img class="logo" src="/ad-astra.svg" alt="Ad Astra" width="40" height="40" />
	{#each MAIN_NAV as item (item.href)}{@render link(item)}{/each}
	<div class="spacer"></div>
	<SyncItem />
	{#each BOTTOM_NAV as item (item.href)}{@render link(item)}{/each}
</nav>

<style>
	.sidebar {
		position: fixed; top: 0; left: 0; bottom: 0; width: var(--sidebar-w); z-index: 20;
		display: flex; flex-direction: column; align-items: center; padding: 12px 0;
		background: rgba(12, 15, 28, 0.6); border-right: 1px solid var(--glass-border);
		backdrop-filter: blur(var(--glass-blur));
	}
	.logo { margin-bottom: 12px; }
	.spacer { flex: 1; }
	.item {
		position: relative; width: 100%; display: flex; flex-direction: column; align-items: center; gap: 3px;
		padding: 7px 0; color: var(--cream-dim); text-decoration: none; font-size: 10.5px;
	}
	.item:hover, .item:focus-visible { color: var(--cream); }
	.item.active { color: var(--gold); }
	.item.active :global(svg) { filter: drop-shadow(0 0 6px rgba(232, 207, 156, 0.65)); }
	.item.active::before {
		content: ''; position: absolute; left: 0; top: 8px; bottom: 8px; width: 3px; border-radius: 2px; background: var(--gold);
	}
</style>
