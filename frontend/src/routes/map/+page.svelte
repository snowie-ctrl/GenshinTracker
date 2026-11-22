<script lang="ts">
	import { onMount } from 'svelte';
	import { api, errorMessage } from '$lib/api';
	import { initialTab, loadLastMap, nextTab, saveLastMap } from '$lib/maps';
	import type { MapKey, MapsResponse } from '$lib/types';
	import Icon from '$lib/Icon.svelte';

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

	// roving tabindex: arrows (and Home/End) select and focus the neighbouring tab
	function keydown(e: KeyboardEvent) {
		if (!data) return;
		const key = nextTab(data.maps.map((m) => m.key), tab, e.key);
		if (key === null) return;
		e.preventDefault();
		choose(key);
		document.getElementById(`map-tab-${key}`)?.focus();
	}
</script>

<div class="map-page">
	{#if error}<p class="error">{error}</p>{/if}
	{#if data}
		<div class="bar glass">
			<h1>Map</h1>
			<div class="tabs" role="tablist" aria-label="Maps">
				{#each data.maps as m (m.key)}
					<button type="button" role="tab" class="chip" class:on={tab === m.key} aria-selected={tab === m.key}
						id="map-tab-{m.key}" aria-controls="map-panel" tabindex={tab === m.key ? 0 : -1} onkeydown={keydown}
						data-testid="map-tab-{m.key}" onclick={() => choose(m.key)}>{m.name}</button>
				{/each}
			</div>
			{#if current}
				<a class="open" href={current.url} target="_blank" rel="noopener noreferrer">
					Open in new tab <Icon name="external" size={14} />
				</a>
			{/if}
		</div>
		{#if current}
			<div class="panel-area" role="tabpanel" id="map-panel" aria-labelledby="map-tab-{current.key}">
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
</div>

<style>
	.map-page { flex: 1; min-height: 600px; display: flex; flex-direction: column; gap: 10px; }
	.bar { display: flex; align-items: center; gap: 14px; padding: 8px 14px; }
	.bar h1 { margin: 0; font-size: 18px; }
	.tabs { display: flex; gap: 6px; }
	.open { margin-left: auto; display: inline-flex; align-items: center; gap: 6px; }
	.panel-area { flex: 1; min-height: 0; display: flex; flex-direction: column; }
	iframe { flex: 1; width: 100%; min-height: 540px; border: 1px solid var(--glass-border); border-radius: 12px; background: var(--glass-bg-strong); }
	.fallback { text-align: center; padding: 40px; }
	.big { display: inline-block; margin-top: 10px; padding: 10px 18px; border-radius: 8px; background: var(--gold);
		color: #17130b; font-weight: 600; text-decoration: none; }
</style>
