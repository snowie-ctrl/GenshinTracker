<script lang="ts">
	import { sourceLabel } from './artifacts';
	import { imgSrc } from './img';
	import type { ArtifactSetOption } from './types';

	let { index, options, value, onchange }: {
		index: number; options: ArtifactSetOption[]; value: number | null; onchange: (id: number | null) => void;
	} = $props();
	const chosen = $derived(options.find((o) => o.id === value));
</script>

<div class="picker">
	<div class="icon">{#if chosen && imgSrc(chosen.icon)}<img src={imgSrc(chosen.icon)} alt="" />{/if}</div>
	<div class="body">
		<select aria-label="Artifact set {index + 1}" data-testid="artifact-set-{index}" value={value ?? ''}
			onchange={(e) => onchange(e.currentTarget.value === '' ? null : Number(e.currentTarget.value))}>
			<option value="">Choose a set…</option>
			{#each options as o (o.id)}<option value={o.id}>{o.name}</option>{/each}
		</select>
		{#if value !== null}
			<span class="muted small" data-testid="artifact-source-{index}">{sourceLabel(chosen)}</span>
		{/if}
	</div>
</div>

<style>
	.picker { display: flex; gap: 8px; align-items: center; }
	.icon { width: 44px; height: 44px; border-radius: 8px; background: rgba(255, 255, 255, 0.06); }
	.icon img { width: 44px; height: 44px; }
	.body { display: flex; flex-direction: column; gap: 2px; }
	.small { font-size: 11px; }
</style>
