<script lang="ts">
	import { getCharacterPage } from '$lib/characterPage.svelte';
	import { imgSrc } from '$lib/img';
	import { buildValue, scalingColumns } from '$lib/kit';
	import GuideLink from '$lib/GuideLink.svelte';
	import KitText from '$lib/KitText.svelte';
	import ScalingTable from '$lib/ScalingTable.svelte';
	import type { KitTalent, TalentRole } from '$lib/types';

	const p = getCharacterPage();
	const c = $derived(p.c!);
	const owned = $derived(c.constellation ?? 0);
	const KIND: Record<string, string> = { normal: 'Normal Attack', skill: 'Elemental Skill', burst: 'Elemental Burst', other: 'Other' };

	function columns(t: KitTalent) {
		if (t.role === 'other') return [];
		const role = t.role as TalentRole;
		const now = c.owned && c.talents ? { base: c.talents[role], constellation: owned } : null;
		const target = c.goal === 'build' && c.targets
			? { base: c.targets[role], constellation: Math.max(owned, buildValue(c.targets.constellation, owned)) }
			: null;
		return scalingColumns(p.kit, role, now, target);
	}
	function kind(t: KitTalent): string {
		const parts = [KIND[t.role]];
		if (t.cooldown !== null) parts.push(`CD ${t.cooldown}s`);
		if (t.cost !== null) parts.push(`${t.cost} Energy`);
		return parts.join(' · ');
	}
</script>

<GuideLink slug={c.slug} />

{#if p.kitState === 'loading'}
	<p class="muted">Loading talents…</p>
{:else if !p.kit}
	<div class="card" data-testid="kit-unavailable">
		<p>Talent data unavailable.</p>
		<button type="button" onclick={() => p.loadKit(p.slug)}>Retry</button>
	</div>
{:else}
	{#if p.kitState === 'stale'}<p class="muted" data-testid="kit-stale">Talent data may be out of date.</p>{/if}
	<div class="two">
		<div>
			<section class="card" data-testid="guide-talents">
				<h2>Talents</h2>
				{#each p.kit.talents as t, i (i)}
					{@const cols = columns(t)}
					<div class="t">
						<div class="ic">{#if imgSrc(t.icon)}<img src={imgSrc(t.icon)} alt="" />{/if}</div>
						<div>
							<b class="name">{t.name}</b><span class="k">{kind(t)}</span>
							<KitText lines={t.description} />
							{#if cols.length}<ScalingTable rows={t.scaling} columns={cols} />{/if}
						</div>
					</div>
				{/each}
			</section>
			<section class="card gap">
				<h2>Passives</h2>
				{#each p.kit.passives as ps, i (i)}
					<div class="t">
						<div class="ic">{#if imgSrc(ps.icon)}<img src={imgSrc(ps.icon)} alt="" />{/if}</div>
						<div><b class="name">{ps.name}</b><KitText lines={ps.description} /></div>
					</div>
				{/each}
			</section>
		</div>
		<section class="card" data-testid="guide-constellations">
			<h2>Constellations · C{owned}</h2>
			{#each p.kit.constellations as k (k.index)}
				<div class="cons" class:off={k.index > owned}>
					<div class="ic small">{#if imgSrc(k.icon)}<img src={imgSrc(k.icon)} alt="" />{/if}</div>
					<div><b>C{k.index} · {k.name}</b><KitText lines={k.description} /></div>
				</div>
			{/each}
		</section>
	</div>
{/if}

<style>
	.two { display: grid; grid-template-columns: 1.4fr 1fr; gap: 12px; align-items: start; }
	.gap { margin-top: 12px; }
	.t, .cons { display: flex; gap: 12px; margin-bottom: 14px; }
	.ic { flex: 0 0 48px; height: 48px; border-radius: 50%; background: rgba(255, 255, 255, 0.07);
		border: 1px solid var(--glass-border); display: flex; align-items: center; justify-content: center; }
	.ic img { width: 40px; height: 40px; }
	.ic.small { flex-basis: 40px; height: 40px; border-color: var(--el, var(--gold)); }
	.ic.small img { width: 32px; height: 32px; }
	.cons.off .ic.small { border-color: var(--glass-border); }
	.cons.off img { opacity: 0.3; filter: grayscale(1); }
	.name { color: var(--el, var(--cream)); }
	.k { font-size: 11px; color: var(--muted); margin-left: 6px; }
	@media (max-width: 1100px) { .two { grid-template-columns: 1fr; } }
</style>
