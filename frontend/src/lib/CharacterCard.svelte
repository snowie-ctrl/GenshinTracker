<script lang="ts">
	import GoalSwitch from './GoalSwitch.svelte';
	import { imgSrc } from './img';
	import { progressTooltip, statusLine } from './status';
	import type { Character, Goal } from './types';

	let { character, onGoal }: { character: Character; onGoal: (g: Goal) => void } = $props();

	const src = $derived(imgSrc(character.icon));
	const pct = $derived(Math.round((character.progress ?? 0) * 100));
</script>

<div class="card r{character.rarity} st-{character.status}" data-testid="card-{character.slug}">
	<a href="/characters/{character.slug}" class="body" aria-label={character.name}>
		{#if src}<img {src} alt="" loading="lazy" />{:else}<div class="ph">?</div>{/if}
		<div class="name">{character.name}</div>
		{#if character.status === 'building'}
			<div
				class="bar"
				role="progressbar"
				aria-valuemin={0}
				aria-valuemax={100}
				aria-valuenow={pct}
				title={progressTooltip(character)}
			>
				<i style="width: {pct}%"></i>
			</div>
		{:else}
			<div class="sub">{statusLine(character)}</div>
		{/if}
	</a>
	<div class="switch">
		<GoalSwitch goal={character.goal} onchange={onGoal} compact />
	</div>
</div>

<style>
	.card { position: relative; width: 104px; border-radius: 10px; overflow: hidden; background: var(--panel-2); }
	.body { display: block; color: var(--text); text-decoration: none; }
	img, .ph { width: 104px; height: 104px; display: block; background: var(--r0); }
	.r5 img, .r5 .ph { background: var(--r5); }
	.r4 img, .r4 .ph { background: var(--r4); }
	.ph { display: grid; place-items: center; font-size: 32px; color: var(--muted); }
	.name { font-size: 12px; text-align: center; padding: 4px 4px 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.sub { font-size: 11px; color: var(--muted); text-align: center; min-height: 20px; padding-bottom: 4px; }
	.bar { height: 5px; margin: 6px 8px 9px; background: #444; border-radius: 3px; }
	.bar i { display: block; height: 100%; background: var(--building); border-radius: 3px; }
	.st-building { outline: 2px solid var(--building); outline-offset: -2px; }
	.st-wanted { opacity: 0.85; }
	.st-unobtained img { filter: grayscale(1); opacity: 0.45; }
	.switch {
		position: absolute; top: 4px; left: 0; right: 0; display: flex; justify-content: center;
		opacity: 0; transition: opacity 0.12s;
	}
	.card:hover .switch, .card:focus-within .switch { opacity: 1; }
</style>
