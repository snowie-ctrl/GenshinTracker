<script lang="ts">
	import { elementStyle } from './elements';
	import { imgSrc } from './img';
	import { RIBBON_DEG, slantInset, talentParts } from './teams';
	import type { TeamMember } from './types';

	let { member: m, onBuildAgain }: { member: TeamMember | null; onBuildAgain: (m: TeamMember) => void } = $props();

	const INFO_H = 150;                                   // fixed info block height (px) so the inset is known
	const inset = slantInset(INFO_H) + 10;
	const el = $derived(elementStyle(m?.element));
	const splash = $derived(m ? imgSrc(m.splash) : null);
</script>

<div class="rib" class:unowned={m && !m.owned} class:empty={!m} style="--sk: -{RIBBON_DEG}deg; --el: {el.color}; --inset: {inset}px; --info-h: {INFO_H}px"
	data-testid={m ? `ribbon-${m.slug ?? m.id}` : undefined}>
	{#if m}
		<div class="bg"></div>
		{#if splash}<div class="art" style="background-image: url({splash})"></div>{/if}
		<div class="shade"></div>
		<div class="info">
			<div class="nm">{#if el.icon}<img src={imgSrc(el.icon)} alt="" />{/if}<span>{m.name}</span>
				{#if m.owned && m.constellation !== null}<span class="muted">C{m.constellation}</span>{/if}</div>
			{#if m.owned}
				<div class="line"><span>Lv {m.level}</span>{#if m.talents}<span class="dim">·</span><span>{#each talentParts(m.talents) as p, i (i)}{#if i}/{/if}<span class:crown={p.crowned}>{p.value}</span>{/each}</span>{/if}</div>
				{#if m.weapon}<div class="line">{#if imgSrc(m.weapon.icon)}<img class="wp" src={imgSrc(m.weapon.icon)} alt="" />{/if}<span>Lv {m.weapon.level} R{m.weapon.refinement}</span></div>{/if}
				{#if m.artifact_sets.length}
					<div class="line" title={m.artifact_line}>
						{#each m.artifact_sets as a (a.name)}
							<span class="set" title="{a.pieces}pc {a.name}">{#if a.icon}<img src={imgSrc(a.icon)} alt="" />{:else}<span class="noicon">?</span>{/if}<b>{a.pieces}</b></span>
						{/each}
					</div>
				{/if}
			{:else}
				<div class="line"><span class="badge">Not owned</span></div>
			{/if}
			{#if m.role}<div class="role">{m.role}</div>{/if}
			{#if m.not_building}
				<div class="warn">Not building {#if m.slug !== null}<button type="button" onclick={(e) => { e.stopPropagation(); onBuildAgain(m); }}>Build again</button>{/if}</div>
			{/if}
			{#if m.not_calculated}<div class="muted small">Not calculated</div>{/if}
		</div>
	{:else}
		<div class="plus" aria-hidden="true">+</div>
	{/if}
</div>

<style>
	.rib { position: relative; overflow: hidden; transform: skewX(var(--sk)); height: 100%;
		border-left: 1px solid rgba(255, 255, 255, 0.15); border-right: 1px solid rgba(255, 255, 255, 0.15); }
	.bg { position: absolute; inset: 0; background: linear-gradient(180deg, color-mix(in srgb, var(--el) 55%, #0b0e1a) 0%, #0b0e1a 85%); }
	.art { position: absolute; top: 0; bottom: 0; left: -45%; right: -45%; transform: skewX(calc(var(--sk) * -1));
		background-repeat: no-repeat; background-size: auto 125%; background-position: center 20%; }
	.unowned .art { filter: grayscale(1) brightness(0.55); }
	.unowned .bg { background: linear-gradient(180deg, #2a2d38, #0b0e1a 85%); }
	.unowned .nm img { filter: grayscale(1); }
	.info { position: absolute; left: 0; right: 0; bottom: 0; height: var(--info-h); box-sizing: border-box; overflow: hidden;
		padding: 28px 10px 10px var(--inset); transform: skewX(calc(var(--sk) * -1)); transform-origin: bottom left;
		font-size: 12px; text-align: left; }
	/* The fade lives on the skewed layer so it fills the whole parallelogram, not an upright box. */
	.shade { position: absolute; left: 0; right: 0; bottom: 0; height: calc(var(--info-h) + 30px);
		background: linear-gradient(180deg, transparent, rgba(6, 8, 16, 0.92) 30%); }
	.dim { color: var(--muted); }
	.nm { font-weight: 700; font-size: 14px; display: flex; gap: 5px; align-items: center; white-space: nowrap; }
	.nm span:first-of-type { overflow: hidden; text-overflow: ellipsis; }
	.nm img { width: 16px; height: 16px; }
	.line { display: flex; gap: 6px; align-items: center; margin-top: 3px; white-space: nowrap; }
	.crown { color: var(--gold); font-weight: 700; }
	.wp { width: 24px; height: 24px; }
	.set { position: relative; width: 24px; height: 24px; }
	.set img, .noicon { width: 24px; height: 24px; display: grid; place-items: center; }
	.set b { position: absolute; right: -3px; bottom: -3px; font-size: 9px; background: #10131f; border-radius: 6px; padding: 0 3px; }
	.role { font-style: italic; color: var(--cream-dim, #b9ad95); margin-top: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.badge { font-size: 10px; padding: 1px 6px; border-radius: 8px; background: #3a3f50; color: #cfd3df; }
	.warn { color: var(--warn); margin-top: 3px; }
	.small { font-size: 11px; }
	.empty { border: 2px dashed rgba(255, 255, 255, 0.2); }
	.plus { position: absolute; inset: 0; display: grid; place-items: center; font-size: 32px; color: var(--muted); transform: skewX(calc(var(--sk) * -1)); }
</style>
