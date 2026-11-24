<!-- frontend/src/lib/ShowcasePanel.svelte -->
<script lang="ts">
	import { elementStyle } from './elements';
	import { imgSrc } from './img';
	import { talentLine } from './profile';
	import type { ShowcaseEntry } from './types';

	let { entry }: { entry: ShowcaseEntry } = $props();
	const SLOTS = ['Flower', 'Plume', 'Sands', 'Goblet', 'Circlet'];
	const tint = $derived(elementStyle(entry.element).color);
</script>

<div class="detail" style="--tint: {tint}" data-testid="showcase-panel" aria-live="polite">
	<div class="who">
		{#if imgSrc(entry.icon)}<img class="portrait" src={imgSrc(entry.icon)} alt="" />{/if}
		<h3>{entry.name}</h3>
		<div class="muted">Lv {entry.level} · C{entry.constellation} · ♥ {entry.friendship}</div>
		<div class="talents" title="Normal attack / Skill / Burst">Talents {talentLine(entry.talents)}</div>
		<div class="weapon">
			{#if imgSrc(entry.weapon.icon)}<img src={imgSrc(entry.weapon.icon)} alt="" />{/if}
			<span>{entry.weapon.name}<br /><span class="muted">Lv {entry.weapon.level} · R{entry.weapon.refinement}</span></span>
		</div>
		{#if entry.slug}<a href="/characters/{entry.slug}">Open character</a>{/if}
	</div>
	<dl class="stats">
		{#each entry.stats as s (s.name)}<dt>{s.name}</dt><dd>{s.value}</dd>{/each}
	</dl>
	<div class="arts">
		{#if entry.artifacts.length === 0}
			<p class="muted">No artifacts synced.</p>
		{:else}
			<div class="muted small">{entry.sets || 'Mixed sets'} · CV {entry.crit_value}</div>
			<div class="grid">
				{#each entry.artifacts as a (a.slot)}
					<div class="art">
						{#if imgSrc(a.icon)}<img src={imgSrc(a.icon)} alt="" />{/if}
						<div class="muted small">{SLOTS[a.slot - 1] ?? `Slot ${a.slot}`} · +{a.level}</div>
						<strong>{a.main_stat}</strong>
						{#each a.substats as sub, i (i)}<div class="small">{sub}</div>{/each}
					</div>
				{/each}
			</div>
		{/if}
	</div>
</div>

<style>
	.detail { display: grid; grid-template-columns: 180px minmax(200px, 320px) 1fr; gap: 16px; margin-top: 12px; padding: 12px;
		border-radius: 12px; border: 1px solid color-mix(in srgb, var(--tint) 50%, transparent);
		background: linear-gradient(90deg, color-mix(in srgb, var(--tint) 22%, transparent), transparent); }
	@media (max-width: 900px) { .detail { grid-template-columns: 1fr; } }
	.portrait { width: 96px; height: 96px; border-radius: 12px; }
	h3 { margin: 6px 0 2px; }
	.talents { margin: 6px 0; font-size: 12px; }
	.weapon { display: flex; align-items: center; gap: 6px; font-size: 12px; margin-bottom: 6px; }
	.weapon img { width: 32px; height: 32px; }
	.stats { display: grid; grid-template-columns: 1fr auto; gap: 2px 12px; margin: 0; font-size: 13px; align-content: start; }
	.stats dt { color: var(--muted); }
	.stats dd { margin: 0; font-weight: 600; text-align: right; font-variant-numeric: tabular-nums; }
	.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 6px; margin-top: 6px; }
	.art { background: var(--panel-2); border-radius: 8px; padding: 6px; font-size: 12px; }
	.art img { width: 32px; height: 32px; float: right; }
	.small { font-size: 11px; }
</style>
