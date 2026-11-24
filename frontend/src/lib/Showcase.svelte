<!-- frontend/src/lib/Showcase.svelte -->
<script lang="ts">
	import { RARITY_STYLE, elementStyle } from './elements';
	import { imgSrc } from './img';
	import ShowcaseEditor from './ShowcaseEditor.svelte';
	import ShowcasePanel from './ShowcasePanel.svelte';
	import type { OwnedOption, ShowcaseEntry } from './types';

	let { entries, mode, owned, onsave }: {
		entries: ShowcaseEntry[]; mode: 'auto' | 'custom'; owned: OwnedOption[]; onsave: (ids: number[]) => Promise<void>;
	} = $props();
	let openId = $state<number | null>(null);
	let editing = $state(false);
	const current = $derived(entries.find((e) => e.id === openId) ?? entries[0] ?? null);

	async function save(ids: number[]) {
		await onsave(ids);
		editing = false;
	}
</script>

<section class="panel" data-testid="showcase">
	<div class="head">
		<h2>Showcase <span class="muted small">{mode === 'auto' ? 'automatic' : 'your pick'}</span></h2>
		<button type="button" onclick={() => (editing = true)}>Edit showcase</button>
	</div>
	<div class="row">
		{#each entries as e (e.id)}
			{@const el = elementStyle(e.element)}
			<button type="button" class="card" data-testid="showcase-card" aria-pressed={current?.id === e.id}
				style="--rar: {RARITY_STYLE[e.rarity ?? 0]?.color ?? 'var(--pill-neutral)'}" onclick={() => (openId = e.id)}>
				{#if imgSrc(e.icon)}<img class="face" src={imgSrc(e.icon)} alt="" />{:else}<span class="face initial">{e.name.slice(0, 1)}</span>{/if}
				{#if el.icon && imgSrc(el.icon)}<img class="el" src={imgSrc(el.icon)} alt={e.element ?? ''} />{/if}
				<strong>{e.name}</strong>
				<span class="muted small">Lv {e.level} · C{e.constellation}</span>
			</button>
		{/each}
	</div>
	{#if current}<ShowcasePanel entry={current} />{/if}
</section>

{#if editing}
	<ShowcaseEditor {owned} initial={entries.map((e) => e.id)} onsave={save} onclose={() => (editing = false)} />
{/if}

<style>
	.head { display: flex; align-items: center; justify-content: space-between; }
	.row { display: grid; grid-template-columns: repeat(8, minmax(0, 1fr)); gap: 8px; }
	@media (max-width: 900px) { .row { grid-template-columns: repeat(4, minmax(0, 1fr)); } }
	.card { all: unset; cursor: pointer; position: relative; display: flex; flex-direction: column; align-items: center;
		text-align: center; border-radius: 10px; overflow: hidden; padding-bottom: 6px; font-size: 12px;
		background: linear-gradient(180deg, color-mix(in srgb, var(--rar) 60%, transparent), var(--panel-2)); }
	.card[aria-pressed='true'] { outline: 2px solid var(--avg-pity); }
	.card:focus-visible { outline: 2px solid var(--avg-pity); }
	.face { width: 100%; aspect-ratio: 1; object-fit: cover; }
	.initial { display: flex; align-items: center; justify-content: center; font-size: 28px; font-weight: 700; }
	.el { position: absolute; top: 4px; right: 4px; width: 18px; height: 18px; }
	.small { font-size: 11px; }
</style>
