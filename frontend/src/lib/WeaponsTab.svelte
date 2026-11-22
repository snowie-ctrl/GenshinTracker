<script lang="ts">
	import { api, errorMessage } from './api';
	import { filterWeapons, holderLabel, isUnequipped, type WeaponFilter } from './good';
	import { imgSrc } from './img';
	import type { GoodWeapon } from './types';

	let { version }: { version: string } = $props();
	let weapons = $state<GoodWeapon[]>([]);
	let error = $state<string | null>(null);
	let f = $state<WeaponFilter>({ type: '', rarity: 0, unequippedOnly: false, query: '' });

	$effect(() => {
		void version;
		api.goodWeapons().then((w) => { weapons = w; error = null; }).catch((e) => (error = errorMessage(e)));
	});
	const types = $derived([...new Set(weapons.map((w) => w.weapon_type))].sort());
	const shown = $derived(filterWeapons(weapons, f));
</script>

{#if error}<p class="error">{error}</p>{/if}
<div class="bar">
	<select aria-label="Weapon type" bind:value={f.type}>
		<option value="">All types</option>
		{#each types as t (t)}<option value={t}>{t}</option>{/each}
	</select>
	<select aria-label="Rarity" bind:value={f.rarity}>
		<option value={0}>Any rarity</option>
		{#each [5, 4, 3, 2, 1] as r (r)}<option value={r}>{r}★</option>{/each}
	</select>
	<label class="inline"><input type="checkbox" bind:checked={f.unequippedOnly} /> Unequipped only</label>
	<input type="search" placeholder="Search weapons" aria-label="Search weapons" bind:value={f.query} />
	<span class="muted">{shown.length} of {weapons.length} · holders as of scan</span>
</div>
<div class="grid">
	{#each shown as w (w.id)}
		<div class="card" data-testid="weapon-card">
			<div class="face r{w.rarity}">{#if imgSrc(w.icon)}<img src={imgSrc(w.icon)} alt="" loading="lazy" />{/if}</div>
			<div class="name">{w.name}</div>
			<div class="muted">Lv {w.level} · R{w.refinement}</div>
			<div class="holder" class:free={isUnequipped(w)}>
				{#if w.holder && imgSrc(w.holder.icon)}<img src={imgSrc(w.holder.icon)} alt="" class="avatar" />{/if}
				{holderLabel(w)}
			</div>
		</div>
	{/each}
</div>

<style>
	.bar { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-bottom: 12px; }
	label.inline { display: inline-flex; gap: 6px; align-items: center; font-size: 12px; }
	.grid { display: flex; flex-wrap: wrap; gap: 10px; }
	.card { width: 96px; text-align: center; font-size: 12px; }
	.face { width: 64px; height: 64px; margin: 0 auto; border-radius: 8px; background: var(--r0); }
	.face.r1 { background: var(--r1); } .face.r2 { background: var(--r2); } .face.r3 { background: var(--r3); }
	.face.r4 { background: var(--r4); } .face.r5 { background: var(--r5); }
	.face img { width: 64px; height: 64px; display: block; }
	.name { line-height: 1.2; }
	.holder { display: flex; gap: 4px; align-items: center; justify-content: center; color: var(--muted); }
	.holder.free { color: var(--warn); }
	.avatar { width: 18px; height: 18px; border-radius: 50%; }
</style>
