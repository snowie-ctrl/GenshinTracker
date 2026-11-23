<script lang="ts">
	import { RARITY_STYLE, elementStyle } from './elements';
	import FilterPill from './FilterPill.svelte';
	import { ELEMENTS, WEAPON_TYPES, type Filters, type SortKeys } from './status';

	let { filters = $bindable(), sort = $bindable(), size = $bindable() }: {
		filters: Filters; sort: SortKeys; size?: 'small' | 'large';
	} = $props();

	function toggle<T>(list: T[], value: T): T[] {
		return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
	}
	const SORTS: { key: keyof SortKeys; label: string }[] = [
		{ key: 'az', label: 'A–Z' }, { key: 'rarity', label: 'Rarity' }, { key: 'level', label: 'Level' }
	];
</script>

<div class="bar">
	<input placeholder="Search name" bind:value={filters.search} aria-label="Search characters" />
	{#each ELEMENTS as el (el)}
		<FilterPill label={el} on={filters.elements.includes(el)} color={elementStyle(el).color}
			image={elementStyle(el).icon} onclick={() => (filters.elements = toggle(filters.elements, el))} />
	{/each}
	{#each WEAPON_TYPES as w (w)}
		<FilterPill label={w} on={filters.weapons.includes(w)} onclick={() => (filters.weapons = toggle(filters.weapons, w))} />
	{/each}
	{#each [5, 4] as r (r)}
		<FilterPill label="{r}★" on={filters.rarities.includes(r)} color={RARITY_STYLE[r].color} ink={RARITY_STYLE[r].ink}
			onclick={() => (filters.rarities = toggle(filters.rarities, r))} />
	{/each}
	<span class="sep muted">Sort</span>
	{#each SORTS as s (s.key)}
		<FilterPill label={s.label} on={sort[s.key]} color="var(--gold)" onclick={() => (sort = { ...sort, [s.key]: !sort[s.key] })} />
	{/each}
	{#if size !== undefined}
		<span class="sep muted">Tiles</span>
		<FilterPill label="Small" on={size === 'small'} color="var(--gold)" onclick={() => (size = 'small')} />
		<FilterPill label="Large" on={size === 'large'} color="var(--gold)" onclick={() => (size = 'large')} />
	{/if}
</div>

<style>
	.bar { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-bottom: 12px; }
	input { width: 180px; }
	.sep { margin-left: 10px; font-size: 12px; text-transform: uppercase; letter-spacing: 0.06em; }
</style>
