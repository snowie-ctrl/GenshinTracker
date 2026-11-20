<script lang="ts">
	import type { Snippet } from 'svelte';
	import { imgSrc } from './img';
	import type { TileView } from './materials';

	let { name, icon, rarity, view, dim = false, testid, popover }: {
		name: string; icon: string | null; rarity: number; view: TileView; dim?: boolean; testid?: string;
		popover?: Snippet;
	} = $props();
</script>

<div class="tile" class:dim data-testid={testid}>
	<button type="button" class="face r{rarity}" aria-label={name}>
		{#if imgSrc(icon)}<img src={imgSrc(icon)} alt="" loading="lazy" />{/if}
		{#if view.badge}<span class="badge">{view.badge}</span>{/if}
	</button>
	<div class="count {view.tone}">{view.main}</div>
	{#if view.hint}<div class="hint">{view.hint}</div>{/if}
	<div class="name">{name}</div>
	{#if popover}<div class="popover" role="tooltip">{@render popover()}</div>{/if}
</div>

<style>
	.tile { position: relative; width: 76px; text-align: center; font-size: 12px; }
	.tile.dim { opacity: 0.45; }
	.face { position: relative; width: 64px; height: 64px; padding: 0; border-radius: 8px; border: none;
		background: var(--r0); cursor: default; }
	.face.r1 { background: var(--r1); } .face.r2 { background: var(--r2); } .face.r3 { background: var(--r3); }
	.face.r4 { background: var(--r4); } .face.r5 { background: var(--r5); }
	.face img { width: 64px; height: 64px; display: block; }
	.badge { position: absolute; top: -6px; right: -6px; background: var(--error); color: #fff;
		border-radius: 10px; padding: 1px 6px; font-weight: 700; font-size: 11px; }
	.count { font-weight: 600; min-height: 16px; }
	.count.short { color: var(--error); } .count.met { color: var(--accent); }
	.hint { color: var(--warn); font-size: 11px; }
	.name { color: var(--muted); font-size: 11px; line-height: 1.2; overflow: hidden; display: -webkit-box;
		-webkit-line-clamp: 2; line-clamp: 2; -webkit-box-orient: vertical; }
	.popover { display: none; position: absolute; z-index: 20; top: 70px; left: 50%; transform: translateX(-50%);
		width: 220px; text-align: left; background: var(--panel-2); border: 1px solid var(--line);
		border-radius: 8px; padding: 10px; box-shadow: 0 6px 20px rgba(0, 0, 0, 0.4); }
	.tile:hover .popover, .tile:focus-within .popover { display: block; }
</style>
