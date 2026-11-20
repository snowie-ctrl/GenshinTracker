<script lang="ts">
	import { weekdayNames } from './materials';
	import type { Material } from './types';

	let { material }: { material: Material } = $props();
</script>

<strong>{material.name}</strong>
{#each material.sources as s, i (i)}
	<div class="muted">
		{#if s.kind === 'domain'}{s.name} · {weekdayNames(s.days)}
		{:else if s.kind === 'weekly_boss'}Weekly boss: {s.name}
		{:else if s.kind === 'region'}Local specialty · {s.name}
		{:else}{s.name}{/if}
	</div>
{/each}
{#if material.characters.length}
	<div class="needers">
		{#each material.characters as c (c.id)}<div>{c.name}: {c.need}</div>{/each}
	</div>
{/if}
{#if material.craftable > 0}<div class="muted">Craft {material.craftable} from spare lower tiers</div>{/if}

<style>
	.needers { margin-top: 6px; }
</style>
