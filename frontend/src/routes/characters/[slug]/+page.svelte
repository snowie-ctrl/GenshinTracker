<script lang="ts">
	import { getCharacterPage } from '$lib/characterPage.svelte';
	import ConstellationRow from '$lib/ConstellationRow.svelte';
	import { imgSrc } from '$lib/img';
	import { boost } from '$lib/kit';
	import TagChip from '$lib/TagChip.svelte';
	import TalentBadge from '$lib/TalentBadge.svelte';
	import TravelerElementCard from '$lib/TravelerElementCard.svelte';
	import type { TalentRole } from '$lib/types';

	const p = getCharacterPage();
	const c = $derived(p.c!);
	const SLOTS: Record<number, string> = { 1: 'Flower', 2: 'Plume', 3: 'Sands', 4: 'Goblet', 5: 'Circlet' };
	const TALENTS: { role: TalentRole; label: string }[] = [
		{ role: 'normal', label: 'Normal' }, { role: 'skill', label: 'Skill' }, { role: 'burst', label: 'Burst' }
	];
	const icon = (role: TalentRole) => p.kit?.talents.find((t) => t.role === role)?.icon ?? null;
	const cons = $derived(c.constellation ?? 0);
</script>

{#if c.traveler}
	<TravelerElementCard info={c.traveler} onsaved={() => p.load(p.slug)} />
{/if}

{#if !c.owned}
	<div class="grid">
		<section class="card"><h2>Current</h2><p class="muted">Not obtained yet.</p></section>
		<section class="card" data-testid="in-teams">{@render teams()}</section>
	</div>
{:else}
	<div class="grid">
		<section class="card">
			<h2>Level</h2>
			<div data-testid="current-level"><span class="big">{c.level}</span> <span class="muted">/ 90 · Friendship {c.friendship}</span></div>
			<h2 class="gap" data-testid="current-constellation">Constellations · C{cons}</h2>
			<ConstellationRow kit={p.kit} owned={cons} />
		</section>
		<section class="card">
			<h2>Talents</h2>
			<div class="talents">
				{#each TALENTS as t (t.role)}
					<TalentBadge testid="talent-{t.role}" icon={icon(t.role)} label={t.label}
						base={c.talents?.[t.role] ?? 1} bonus={boost(p.kit, t.role, cons)} />
				{/each}
			</div>
		</section>
		<section class="card">
			<h2>Weapon</h2>
			{#if c.weapon}
				<div class="weapon">
					{#if imgSrc(c.weapon.icon)}<img src={imgSrc(c.weapon.icon)} alt="" />{/if}
					<div><b>{c.weapon.name}</b><div class="muted">{'★'.repeat(c.weapon.rarity)} · Lv {c.weapon.level} · R{c.weapon.refinement}</div></div>
				</div>
			{:else}<p class="muted">No weapon data.</p>{/if}
			<div class="gap" data-testid="in-teams">{@render teams()}</div>
		</section>
		<section class="card span2">
			<h2>Artifacts</h2>
			<div class="artifacts">
				{#each c.artifacts as a (a.slot)}
					<div class="artifact">
						{#if imgSrc(a.icon)}<img src={imgSrc(a.icon)} alt="" />{/if}
						<div class="muted">{SLOTS[a.slot] ?? `Slot ${a.slot}`} · +{a.level}</div>
						<b>{a.main_stat}</b>
						<ul>{#each a.substats as s (s)}<li>{s}</li>{/each}</ul>
						<div class="muted">{a.set_name}</div>
					</div>
				{:else}<p class="muted">No artifact data yet.</p>{/each}
			</div>
		</section>
		<section class="card">
			<h2>Stats</h2>
			<table><tbody>{#each c.stats as s (s.name)}<tr><td>{s.name}</td><td>{s.value}</td></tr>{/each}</tbody></table>
		</section>
	</div>
{/if}

{#snippet teams()}
	<h2>In teams</h2>
	{#if c.teams.length === 0}<p class="muted">Not in any team</p>{:else}
		<ul class="teams">{#each c.teams as t (t.id)}<li><a href="/teams#team-{t.id}">{t.name}</a> {#each t.tags as tag (tag.id)}<TagChip {tag} />{/each}</li>{/each}</ul>
	{/if}
{/snippet}

<style>
	.big { font-size: 28px; font-weight: 700; color: var(--el, var(--cream)); }
	.gap { margin-top: 14px; }
	.talents { display: flex; gap: 12px; }
	.weapon { display: flex; gap: 10px; align-items: center; }
	.weapon img { width: 56px; height: 56px; border-radius: 8px; background: var(--r4); }
	.artifacts { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 8px; }
	.artifact { background: var(--panel-2); border-radius: 8px; padding: 8px; font-size: 12px; }
	.artifact img { width: 34px; height: 34px; }
	.artifact ul { margin: 4px 0; padding-left: 16px; color: var(--muted); }
	.teams { list-style: none; padding: 0; margin: 0; }
	.teams li { display: flex; gap: 6px; align-items: center; padding: 2px 0; }
	table { width: 100%; font-size: 12px; } td:last-child { text-align: right; }
</style>
