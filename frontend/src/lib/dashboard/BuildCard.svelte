<script lang="ts">
	import MaterialTile from '$lib/MaterialTile.svelte';
	import { buildTileView, covered } from '$lib/dashboard';
	import { imgSrc } from '$lib/img';
	import { notCalculatedLabel } from '$lib/materials';
	import type { BuildCard, GapStatus } from '$lib/types';

	let { card, position, gaps, now, disabled, first, last, onup, ondown }: {
		card: BuildCard; position: number; gaps: GapStatus; now: number; disabled: boolean;
		first: boolean; last: boolean; onup: () => void; ondown: () => void;
	} = $props();
</script>

<div class="card" data-testid="build-card-{card.character.slug}">
	<div class="head">
		<span class="handle" aria-hidden="true">⋮⋮</span>
		<span class="badge">P{position}</span>
		{#if imgSrc(card.character.icon)}<img src={imgSrc(card.character.icon)} alt="" />{/if}
		<div class="who">
			<a class="title" href="/characters/{card.character.slug}">{card.character.name}</a>
			{#if card.progress !== null}
				<div class="bar" role="progressbar" aria-valuenow={Math.round(card.progress * 100)} aria-valuemin={0} aria-valuemax={100}><span style="width: {card.progress * 100}%"></span></div>
			{/if}
		</div>
		<span class="moves">
			<button type="button" aria-label="Move {card.character.name} up" data-move="up" disabled={first} aria-disabled={disabled}
				onclick={() => { if (!disabled) onup(); }}>▲</button>
			<button type="button" aria-label="Move {card.character.name} down" data-move="down" disabled={last} aria-disabled={disabled}
				onclick={() => { if (!disabled) ondown(); }}>▼</button>
		</span>
	</div>
	{#if !card.calculated}
		<p class="muted">{notCalculatedLabel(gaps, now)}</p>
	{:else}
		{#if card.ready}<p class="ok">Ready to level up</p>{/if}
		<div class="tiles-row">
			{#each card.materials as m (m.id)}
				<MaterialTile name={m.name} icon={m.icon} rarity={m.rarity} view={buildTileView(m)} dim={covered(m)}
					testid="build-{card.character.slug}-{m.id}" />
			{/each}
		</div>
	{/if}
</div>

<style>
	.card { background: var(--panel-2); border: 1px solid var(--line); border-radius: 10px; padding: 10px; }
	.head { display: flex; gap: 8px; align-items: center; }
	.handle { cursor: grab; color: var(--muted); user-select: none; }
	.badge { font-weight: 700; color: var(--gold); min-width: 28px; }
	.head img { width: 40px; height: 40px; border-radius: 8px; background: var(--r0); }
	.who { flex: 1; }
	.title { font-weight: 600; }
	.moves { display: inline-flex; gap: 4px; }
	.moves button { background: transparent; border: 1px solid var(--glass-border); color: var(--text); border-radius: 6px; width: 28px; height: 26px; cursor: pointer; }
	.moves button:disabled, .moves button[aria-disabled="true"] { opacity: 0.35; cursor: default; }
	.bar { width: 140px; height: 6px; background: var(--line); border-radius: 3px; overflow: hidden; }
	.bar span { display: block; height: 100%; background: var(--building); }
	.tiles-row { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0; }
	.ok { color: var(--accent); margin: 6px 0 0; }
</style>
