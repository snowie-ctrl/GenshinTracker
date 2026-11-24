<script lang="ts">
	import FilterPill from './FilterPill.svelte';
	import { STAT_LABELS } from './artifacts';

	let { slot, options, selected, onchange }: {
		slot: string; options: string[]; selected: string[]; onchange: (key: string) => void;
	} = $props();
</script>

<div class="row" role="group" aria-label="{slot} main stat">
	<span class="label">{slot[0].toUpperCase() + slot.slice(1)}</span>
	{#each options as key (key)}
		<span data-testid="stat-{slot}-{key}">
			<FilterPill label={STAT_LABELS[key] ?? key} on={selected.includes(key)} color="var(--el, var(--gold))"
				onclick={() => onchange(key)} />
		</span>
	{/each}
</div>

<style>
	.row { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
	.label { width: 64px; font-size: 12px; color: var(--muted); }
</style>
