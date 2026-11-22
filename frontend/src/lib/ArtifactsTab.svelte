<script lang="ts">
	import { api, errorMessage } from './api';
	import {
		ARTIFACT_PAGE, DEFAULT_ARTIFACT_FILTER, SLOT_NAMES, SLOTS, filterArtifacts, holderLabel, isUnequipped,
		statName, statValue, type ArtifactFilter
	} from './good';
	import { imgSrc } from './img';
	import type { GoodArtifact } from './types';

	let { version }: { version: string } = $props();
	let artifacts = $state<GoodArtifact[]>([]);
	let error = $state<string | null>(null);
	let f = $state<ArtifactFilter>({ ...DEFAULT_ARTIFACT_FILTER });
	let limit = $state(ARTIFACT_PAGE);

	$effect(() => {
		void version;
		api.goodArtifacts().then((a) => { artifacts = a; error = null; }).catch((e) => (error = errorMessage(e)));
	});
	$effect(() => { void [f.setId, f.slot, f.mainStat, f.unequippedOnly, f.minRarity]; limit = ARTIFACT_PAGE; });
	const sets = $derived([...new Map(artifacts.map((a) => [a.set_id, a.set_name])).entries()].sort((a, b) => a[1].localeCompare(b[1])));
	const mainStats = $derived([...new Set(artifacts.map((a) => a.main_stat))].sort());
	const shown = $derived(filterArtifacts(artifacts, f));
	const unequipped = $derived(artifacts.filter(isUnequipped).length);
</script>

{#if error}<p class="error">{error}</p>{/if}
<p class="muted" data-testid="artifact-count">{artifacts.length} artifacts · {unequipped} unequipped</p>
<div class="bar">
	<select aria-label="Set" bind:value={f.setId}>
		<option value={0}>All sets</option>
		{#each sets as [id, name] (id)}<option value={id}>{name}</option>{/each}
	</select>
	<select aria-label="Slot" bind:value={f.slot}>
		<option value="">All slots</option>
		{#each SLOTS as s (s)}<option value={s}>{SLOT_NAMES[s]}</option>{/each}
	</select>
	<select aria-label="Main stat" bind:value={f.mainStat}>
		<option value="">Any main stat</option>
		{#each mainStats as k (k)}<option value={k}>{statName(k)}</option>{/each}
	</select>
	<select aria-label="Minimum rarity" bind:value={f.minRarity}>
		{#each [5, 4, 3, 1] as r (r)}<option value={r}>{r}★+</option>{/each}
	</select>
	<label class="inline"><input type="checkbox" bind:checked={f.unequippedOnly} /> Unequipped only</label>
	<span class="muted">{shown.length} shown</span>
</div>
<div class="list">
	{#each shown.slice(0, limit) as a (a.id)}
		<div class="card" data-testid="artifact-card">
			<div class="face r{a.rarity}">{#if imgSrc(a.icon)}<img src={imgSrc(a.icon)} alt="" loading="lazy" />{/if}</div>
			<div class="body">
				<div><b>{a.set_name}</b> · {SLOT_NAMES[a.slot]} · {'★'.repeat(a.rarity)} · +{a.level}</div>
				<div>{statName(a.main_stat)}</div>
				<ul>{#each a.substats as s (s.key)}<li>{statName(s.key)} +{statValue(s.key, s.value)}</li>{/each}</ul>
				<div class="holder" class:free={isUnequipped(a)}>
					{#if a.holder && imgSrc(a.holder.icon)}<img src={imgSrc(a.holder.icon)} alt="" class="avatar" />{/if}
					{holderLabel(a)}
				</div>
			</div>
		</div>
	{/each}
</div>
{#if shown.length > limit}
	<button type="button" onclick={() => (limit += ARTIFACT_PAGE)}>Show more ({shown.length - limit} left)</button>
{/if}

<style>
	.bar { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-bottom: 12px; }
	label.inline { display: inline-flex; gap: 6px; align-items: center; font-size: 12px; }
	.list { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 10px; }
	.card { display: flex; gap: 10px; padding: 8px; border: 1px solid var(--line); border-radius: 8px; font-size: 12px; }
	.face { width: 56px; height: 56px; flex: none; border-radius: 8px; background: var(--r0); }
	.face.r1 { background: var(--r1); } .face.r2 { background: var(--r2); } .face.r3 { background: var(--r3); }
	.face.r4 { background: var(--r4); } .face.r5 { background: var(--r5); }
	.face img { width: 56px; height: 56px; display: block; }
	ul { margin: 4px 0; padding-left: 16px; color: var(--muted); }
	.holder { display: flex; gap: 4px; align-items: center; color: var(--muted); }
	.holder.free { color: var(--warn); }
	.avatar { width: 18px; height: 18px; border-radius: 50%; }
</style>
