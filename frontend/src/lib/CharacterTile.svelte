<script lang="ts">
	import { elementStyle } from './elements';
	import GoalSwitch from './GoalSwitch.svelte';
	import { imgSrc } from './img';
	import { progressTooltip } from './status';
	import { talentParts } from './teams';
	import type { Character, Goal } from './types';

	let { character: c, size = 'small', onGoal, onpick, picked = false, disabled = false }: {
		character: Character; size?: 'small' | 'large'; onGoal?: (g: Goal) => void;
		onpick?: () => void; picked?: boolean; disabled?: boolean;
	} = $props();

	const src = $derived(imgSrc(c.icon));
	const el = $derived(elementStyle(c.element));
	const pct = $derived(Math.round((c.progress ?? 0) * 100));
	const owned = $derived(c.owned);
	const stars = $derived('★'.repeat(Math.max(0, c.rarity)));
	const line = $derived(owned ? `Lv ${c.level} · C${c.constellation ?? 0}` : c.goal === 'none' ? 'Not owned' : 'Not owned · Wanted');
</script>

{#snippet face()}
	<div class="pic r{c.rarity}">
		{#if src}<img class="art" {src} alt="" loading="lazy" />{:else}<div class="ph">?</div>{/if}
		{#if el.icon && size === 'small'}<img class="el" src={imgSrc(el.icon)} alt="" />{/if}
	</div>
{/snippet}

{#snippet bar()}
	<div class="bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct} title={progressTooltip(c)}>
		<i style="width: {pct}%"></i>
	</div>
{/snippet}

{#snippet body()}
	{#if size === 'small'}
		<div class="name">{c.name}</div>
		{#if c.status === 'building'}{@render bar()}{:else}<div class="sub">{line}</div>{/if}
	{:else}
		<div class="info">
			<div class="name">{#if el.icon}<img class="el-inline" src={imgSrc(el.icon)} alt="" />{/if}{c.name}</div>
			<div class="stars">{stars}</div>
			<div>{line}</div>
			{#if owned && c.talents}
				<div>Talents {#each talentParts(c.talents) as p, i (i)}{#if i}/{/if}<span class:crown={p.crowned}>{p.value}</span>{/each}</div>
			{/if}
			{#if owned && c.weapon}
				<div class="weapon">{#if imgSrc(c.weapon.icon)}<img src={imgSrc(c.weapon.icon)} alt="" />{/if}Lv {c.weapon.level} R{c.weapon.refinement}</div>
			{/if}
			{#if c.status === 'building'}{@render bar()}{/if}
		</div>
	{/if}
{/snippet}

{#if onpick}
	<button type="button" class="tile {size}" class:unowned={!owned} class:picked data-testid="pick-{c.slug}"
		{disabled} onclick={onpick} aria-label="Add {c.name}">
		{@render face()}{@render body()}
	</button>
{:else}
	<div class="tile {size} st-{c.status}" class:unowned={!owned} data-testid="card-{c.slug}">
		<a href="/characters/{c.slug}" class="link" aria-label={c.name}>{@render face()}{@render body()}</a>
		{#if onGoal}<div class="switch"><GoalSwitch goal={c.goal} onchange={onGoal} compact /></div>{/if}
	</div>
{/if}

<style>
	.tile { position: relative; border-radius: 10px; overflow: hidden; background: var(--glass-bg-strong, rgba(18, 22, 38, 0.7));
		color: var(--text); padding: 0; border: none; text-align: center; }
	.link { display: block; color: inherit; text-decoration: none; }
	.small { width: 104px; }
	.small .pic, .small .art, .small .ph { width: 104px; height: 104px; }
	.large { width: 330px; height: 150px; }
	.large .link, button.large { display: flex; height: 100%; text-align: left; }
	.large .pic, .large .art, .large .ph { width: 150px; height: 150px; flex: none; }
	.pic { position: relative; background: var(--r0); }
	.pic.r5 { background: var(--r5); } .pic.r4 { background: var(--r4); }
	.art { display: block; }
	.ph { display: grid; place-items: center; font-size: 32px; color: var(--muted); }
	.el { position: absolute; left: 4px; top: 4px; width: 18px; height: 18px; }
	.name { font-size: 12px; padding: 4px 4px 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.sub { font-size: 11px; color: var(--muted); min-height: 20px; padding-bottom: 4px; }
	.info { padding: 10px; display: flex; flex-direction: column; gap: 3px; font-size: 12px; min-width: 0; }
	.info .name { font-size: 14px; font-weight: 700; padding: 0; display: flex; gap: 5px; align-items: center; }
	.el-inline { width: 16px; height: 16px; }
	.stars { color: var(--rarity-5); font-size: 11px; }
	.crown { color: var(--gold); font-weight: 700; }
	.weapon { display: flex; gap: 6px; align-items: center; }
	.weapon img { width: 24px; height: 24px; }
	.bar { height: 5px; margin: 6px 8px 9px; background: #444; border-radius: 3px; }
	.info .bar { margin: 4px 0 0; }
	.bar i { display: block; height: 100%; background: var(--building); border-radius: 3px; }
	.st-building { outline: 2px solid var(--building); outline-offset: -2px; }
	.unowned .pic { background: #2a2d38; }
	.unowned .art, .unowned .el, .unowned .el-inline { filter: grayscale(1); opacity: 0.5; }
	.switch { position: absolute; top: 4px; left: 0; right: 0; display: flex; justify-content: center; opacity: 0; transition: opacity 0.12s; }
	.tile:hover .switch, .tile:focus-within .switch { opacity: 1; }
	button.tile { cursor: pointer; }
	button.tile:disabled { opacity: 0.55; cursor: default; }
	.picked { outline: 2px solid var(--gold); outline-offset: -2px; }
</style>
