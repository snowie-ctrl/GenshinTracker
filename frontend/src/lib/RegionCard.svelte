<!-- frontend/src/lib/RegionCard.svelte -->
<script lang="ts">
	import { imgSrc } from './img';
	import { ringDash } from './profile';
	import type { RegionView } from './types';

	let { region }: { region: RegionView } = $props();
	let open = $state(false);
</script>

<div class="region" data-testid="region-card">
	<div class="top">
		<svg viewBox="0 0 36 36" class="ring" role="img" aria-label="{region.name}: {region.explored}% explored">
			<circle cx="18" cy="18" r="15" class="track" />
			<circle cx="18" cy="18" r="15" class="fill" stroke-dasharray={ringDash(region.explored)} transform="rotate(-90 18 18)" />
			{#if imgSrc(region.icon)}<image href={imgSrc(region.icon)} x="10" y="10" width="16" height="16" />{/if}
		</svg>
		<div>
			<div class="name">{region.name}</div>
			<div class="big">{region.explored}%</div>
			{#if region.reputation !== null}<div class="muted small">Reputation {region.reputation}</div>{/if}
			{#each region.offerings as o, j (j)}
				<div class="muted small offering">{#if imgSrc(o.icon)}<img src={imgSrc(o.icon)} alt="" />{/if}{o.name} {o.level}</div>
			{/each}
		</div>
	</div>
	{#if region.areas.length}
		<button type="button" class="more" aria-expanded={open} onclick={() => (open = !open)}>
			{open ? 'Hide' : 'Show'} {region.areas.length} areas
		</button>
		{#if open}
			<ul class="areas">
				{#each region.areas as a, i (i)}
					<li><span>{a.name}</span><span class="track-bar"><span style="width: {Math.min(100, a.explored)}%"></span></span>
						<span class="muted">{a.explored}%</span></li>
				{/each}
			</ul>
		{/if}
	{/if}
</div>

<style>
	.region { background: var(--panel-2); border-radius: 10px; padding: 10px 12px; }
	.top { display: flex; gap: 10px; align-items: center; }
	.ring { width: 56px; height: 56px; flex: none; }
	.track { fill: none; stroke: var(--line); stroke-width: 4; }
	.fill { fill: none; stroke: var(--anemo); stroke-width: 4; stroke-linecap: round; }
	.name { font-weight: 600; }
	.big { font-size: 18px; font-weight: 700; }
	.small { font-size: 12px; }
	.offering img { width: 16px; height: 16px; vertical-align: -3px; margin-right: 4px; }
	.more { margin-top: 6px; font-size: 12px; }
	.areas { list-style: none; padding: 0; margin: 6px 0 0; display: grid; gap: 4px; font-size: 12px; }
	.areas li { display: grid; grid-template-columns: 1fr 80px 46px; gap: 6px; align-items: center; }
	.track-bar { height: 6px; background: var(--line); border-radius: 3px; overflow: hidden; }
	.track-bar span { display: block; height: 100%; background: var(--anemo); }
</style>
