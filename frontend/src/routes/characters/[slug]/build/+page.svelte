<script lang="ts">
	import { api } from '$lib/api';
	import BuildArtifacts from '$lib/BuildArtifacts.svelte';
	import BuildSuggestions from '$lib/BuildSuggestions.svelte';
	import { getCharacterPage } from '$lib/characterPage.svelte';
	import ConstellationRow from '$lib/ConstellationRow.svelte';
	import { ownedLabel } from '$lib/good';
	import { imgSrc } from '$lib/img';
	import { buildValue, isReached } from '$lib/kit';
	import type { TalentRole, Targets, WeaponOption } from '$lib/types';

	const p = getCharacterPage();
	const c = $derived(p.c!);
	const editing = $derived(c.goal === 'build');
	const cur = $derived({
		level: c.level ?? 1,
		normal: c.talents?.normal ?? 1, skill: c.talents?.skill ?? 1, burst: c.talents?.burst ?? 1,
		constellation: c.constellation ?? 0,
		weapon_level: c.weapon?.level ?? 1, refinement: c.weapon?.refinement ?? 1
	});
	// Read-only preview before Build: the stored targets if any, else the current values.
	const t = $derived<Targets>(c.targets ?? { level: cur.level, normal: cur.normal, skill: cur.skill, burst: cur.burst,
		weapon_level: cur.weapon_level });
	const tCons = $derived(buildValue(t.constellation, cur.constellation));
	const tRef = $derived(buildValue(t.refinement, cur.refinement));
	const TALENTS: { role: TalentRole; label: string; aria: string }[] = [
		{ role: 'normal', label: 'Normal', aria: 'Target normal attack' },
		{ role: 'skill', label: 'Skill', aria: 'Target elemental skill' },
		{ role: 'burst', label: 'Burst', aria: 'Target elemental burst' }
	];
	const TALENT_LEVELS = Array.from({ length: 10 }, (_, i) => i + 1);
	const WEAPON_LEVELS = [20, 40, 50, 60, 70, 80, 90];
	const levelOptions = $derived([...new Set([...p.caps, t.level])].sort((a, b) => a - b));
	const icon = (role: TalentRole) => p.kit?.talents.find((k) => k.role === role)?.icon ?? null;

	let weapons = $state<WeaponOption[]>([]);
	const weaponType = $derived(c.weapon_type);
	$effect(() => {
		const type = weaponType;
		if (!type) return;
		api.weapons(type).then((w) => (weapons = w)).catch(() => (weapons = []));
	});

	// Rapid successive edits build on the latest unsaved draft, not the stale loaded targets.
	let draft: Targets | null = null;
	let inflight = 0;
	async function save(patch: Partial<Targets>) {
		// constellation/refinement stay as stored (possibly null = same as current) unless this edit sets them.
		draft = { ...(draft ?? t), ...patch };
		inflight++;
		try {
			await p.saveGoal({ targets: draft });
		} finally {
			if (--inflight === 0) draft = null;
		}
	}
	function setWeapon(value: string) {
		p.saveGoal({ planned_weapon_id: value === '' ? null : Number(value) });
	}
</script>

{#if !editing}
	<div class="notice card">
		<span class="muted">Not planned yet. These are the current values.</span>
		<button type="button" data-testid="set-build" onclick={() => p.saveGoal({ goal: 'build' })}>Set to Build</button>
	</div>
{/if}

<div class="grid">
	<section class="card">
		<h2>Level</h2>
		<div class="pair">
			<span class="now">{cur.level}</span><span class="arrow">→</span>
			<select aria-label="Target level" disabled={!editing} value={t.level}
				onchange={(e) => save({ level: Number(e.currentTarget.value) })}>
				{#each levelOptions as l (l)}<option value={l}>{l}</option>{/each}
			</select>
			{#if isReached(cur.level, t.level)}<span class="done" data-testid="reached-level">✓</span>{/if}
		</div>
		<h2 class="gap">Constellations · C{cur.constellation} →
			<select aria-label="Target constellation" disabled={!editing} value={tCons}
				onchange={(e) => save({ constellation: Number(e.currentTarget.value) })}>
				{#each [0, 1, 2, 3, 4, 5, 6] as n (n)}<option value={n}>C{n}</option>{/each}
			</select>
			{#if isReached(cur.constellation, tCons)}<span class="done" data-testid="reached-constellation">✓</span>{/if}
		</h2>
		<ConstellationRow kit={p.kit} owned={cur.constellation} target={tCons} />
		<p class="muted small">Dashed = wanted, not owned yet. Wishes, not farming: the planner ignores it.</p>
	</section>

	<section class="card">
		<h2>Talents</h2>
		<div class="talents">
			{#each TALENTS as k (k.role)}
				<div class="talent">
					<div class="ic">{#if imgSrc(icon(k.role))}<img src={imgSrc(icon(k.role))} alt="" />{/if}</div>
					<div class="pair">
						<span class="now">{cur[k.role]}</span><span class="arrow">→</span>
						<select aria-label={k.aria} disabled={!editing} value={t[k.role]}
							onchange={(e) => save({ [k.role]: Number(e.currentTarget.value) } as Partial<Targets>)}>
							{#each TALENT_LEVELS as l (l)}<option value={l}>{l}</option>{/each}
						</select>
						{#if isReached(cur[k.role], t[k.role])}<span class="done" data-testid={`reached-${k.role}`}>✓</span>{/if}
					</div>
					<span class="muted small">{k.label}</span>
				</div>
			{/each}
		</div>
	</section>

	<section class="card">
		<h2>Weapon</h2>
		<label class="field">
			<span class="muted small">Planned weapon</span>
			<select aria-label="Planned weapon" disabled={!editing} value={c.planned_weapon_id ?? ''}
				onchange={(e) => setWeapon(e.currentTarget.value)}>
				<option value="">{c.owned && c.weapon ? `Equipped: ${c.weapon.name}` : 'None'}</option>
				{#each weapons as w (w.id)}<option value={w.id}>{'★'.repeat(w.rarity)} {w.name}{w.owned ? ` · ${ownedLabel(w.owned)}` : ''}</option>{/each}
			</select>
		</label>
		<div class="pair gap">
			<span class="muted small">Lv {cur.weapon_level} →</span>
			<select aria-label="Target weapon level" disabled={!editing} value={t.weapon_level}
				onchange={(e) => save({ weapon_level: Number(e.currentTarget.value) })}>
				{#each [...new Set([...WEAPON_LEVELS, t.weapon_level])].sort((a, b) => a - b) as l (l)}<option value={l}>{l}</option>{/each}
			</select>
			{#if isReached(cur.weapon_level, t.weapon_level)}<span class="done" data-testid="reached-weapon_level">✓</span>{/if}
			<span class="muted small">R{cur.refinement} →</span>
			<select aria-label="Target refinement" disabled={!editing} value={tRef}
				onchange={(e) => save({ refinement: Number(e.currentTarget.value) })}>
				{#each [1, 2, 3, 4, 5] as r (r)}<option value={r}>R{r}</option>{/each}
			</select>
			{#if isReached(cur.refinement, tRef)}<span class="done" data-testid="reached-refinement">✓</span>{/if}
		</div>
	</section>

	<BuildArtifacts {editing} />

	<BuildSuggestions {editing} />
</div>

<style>
	.notice { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
	.pair { display: flex; gap: 6px; align-items: center; }
	.now { font-size: 20px; font-weight: 700; }
	.arrow { color: var(--el, var(--gold)); font-weight: 700; }
	.done { color: var(--building); }
	.gap { margin-top: 14px; }
	.small { font-size: 11px; }
	.talents { display: flex; gap: 14px; flex-wrap: wrap; }
	.talent { display: flex; flex-direction: column; align-items: center; gap: 4px; }
	.ic { width: 48px; height: 48px; border-radius: 50%; background: rgba(255, 255, 255, 0.07); border: 1px solid var(--glass-border);
		display: flex; align-items: center; justify-content: center; }
	.ic img { width: 40px; height: 40px; }
	.field { display: flex; flex-direction: column; gap: 4px; }
	select:not(:disabled) { border-color: var(--el, var(--glass-border)); }
</style>
