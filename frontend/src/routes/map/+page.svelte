<script lang="ts">
	import { onMount } from 'svelte';
	import { api, errorMessage } from '$lib/api';
	import { initialTab, loadLastMap, saveLastMap } from '$lib/maps';
	import type { MapKey, MapsResponse } from '$lib/types';

	let data = $state<MapsResponse | null>(null);
	let tab = $state<MapKey>('hoyolab');
	let error = $state<string | null>(null);
	const current = $derived(data?.maps.find((m) => m.key === tab) ?? null);

	onMount(async () => {
		try {
			data = await api.maps();
			tab = initialTab(loadLastMap(), data.default_map);
		} catch (e) {
			error = errorMessage(e);
		}
	});

	function choose(key: MapKey) {
		tab = key;
		saveLastMap(key);
	}
</script>

<h1>Map</h1>
{#if error}<p class="error">{error}</p>{/if}
{#if data}
	<div class="tabs" role="tablist" aria-label="Maps">
		{#each data.maps as m (m.key)}
			<button type="button" role="tab" class="chip" class:on={tab === m.key} aria-selected={tab === m.key}
				id="map-tab-{m.key}" aria-controls="map-panel"
				data-testid="map-tab-{m.key}" onclick={() => choose(m.key)}>{m.name}</button>
		{/each}
	</div>
	{#if current}
		<div role="tabpanel" id="map-panel" aria-labelledby="map-tab-{current.key}">
		<div class="bar">
			<span>{current.name}</span>
			<a href={current.url} target="_blank" rel="noopener noreferrer">Open in new tab</a>
		</div>
		{#if current.allowed === false}
			<section class="panel fallback" data-testid="map-fallback">
				<p>This map doesn't allow embedding</p>
				<a class="big" href={current.url} target="_blank" rel="noopener noreferrer">Open in new tab</a>
			</section>
		{:else}
			{#key current.key}
				<iframe data-testid="map-frame" title={current.name} src={current.url}
					referrerpolicy="no-referrer" allow="fullscreen"></iframe>
			{/key}
		{/if}
		</div>
	{/if}
{/if}

<style>
	.tabs { display: flex; gap: 6px; margin-bottom: 8px; }
	.bar { display: flex; justify-content: space-between; align-items: center; padding: 6px 10px;
		background: var(--panel-2); border-radius: 8px 8px 0 0; }
	iframe { width: 100%; height: calc(100vh - 220px); min-height: 480px; border: none; border-radius: 0 0 8px 8px; }
	.fallback { text-align: center; padding: 40px; }
	.big { display: inline-block; margin-top: 10px; padding: 10px 18px; border-radius: 8px; background: var(--accent);
		color: #111; font-weight: 600; text-decoration: none; }
</style>
