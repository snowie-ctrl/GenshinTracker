<script lang="ts">
	import { page } from '$app/state';
	import { api, errorMessage } from '$lib/api';
	import GoalSwitch from '$lib/GoalSwitch.svelte';
	import { imgSrc } from '$lib/img';
	import { sync } from '$lib/sync.svelte';
	import TargetsEditor from '$lib/TargetsEditor.svelte';
	import MaterialTile from '$lib/MaterialTile.svelte';
	import { charTileView, gapLabel, groupByCategory, notCalculatedLabel, shouldPoll } from '$lib/materials';
	import type { CharacterDetail, Goal, Targets, WeaponOption } from '$lib/types';

	let c = $state<CharacterDetail | null>(null);
	let caps = $state<number[]>([20, 40, 50, 60, 70, 80, 90]);
	let error = $state<string | null>(null);
	let saveError = $state<string | null>(null);

	let weapons = $state<WeaponOption[]>([]);
	let now = $state(Date.now());
	const weaponType = $derived(c?.weapon_type ?? null);

	$effect(() => {
		const type = weaponType; // derived: only refetches when the weapon type itself changes
		if (!type) return;
		api.weapons(type).then((w) => (weapons = w)).catch(() => (weapons = []));
	});

	$effect(() => {
		if (!shouldPoll(c?.shortfall?.gaps)) return;
		const t = setTimeout(() => load(page.params.slug ?? ''), 2000);
		return () => clearTimeout(t);
	});

	async function setPlannedWeapon(value: string) {
		if (!c) return;
		try {
			await api.setGoal(c.id, { planned_weapon_id: value === '' ? null : Number(value) });
			saveError = null;
			await load(page.params.slug ?? '');
		} catch (e) {
			saveError = errorMessage(e);
		}
	}

	const SLOTS: Record<number, string> = { 1: 'Flower', 2: 'Plume', 3: 'Sands', 4: 'Goblet', 5: 'Circlet' };

	$effect(() => {
		const slug = page.params.slug ?? '';
		void sync.version;
		load(slug);
	});

	async function load(slug: string) {
		try {
			const [detail, settings] = await Promise.all([api.character(slug), api.settings()]);
			c = detail;
			now = Date.now();
			caps = settings.level_caps;
			error = null;
		} catch (e) {
			error = errorMessage(e);
		}
	}

	async function update(body: { goal?: Goal; targets?: Targets }) {
		if (!c) return;
		try {
			const updated = await api.setGoal(c.id, body);
			c = { ...c, ...updated };
			await load(page.params.slug ?? '');
			saveError = null;
		} catch (e) {
			saveError = errorMessage(e);
		}
	}
</script>

<a href="/characters">← Characters</a>

{#if error}
	<p class="error">{error}</p>
{:else if !c}
	<p class="muted">Loading…</p>
{:else}
	<header class="hero r{c.rarity}">
		{#if imgSrc(c.splash)}<img src={imgSrc(c.splash)} alt="" />{/if}
		<div class="info">
			<h1>{c.name}</h1>
			<div class="muted">
				{'★'.repeat(c.rarity || 0)} · {c.element ?? '—'} · {c.weapon_type ?? '—'}
			</div>
			<div class="goal">
				<GoalSwitch goal={c.goal} onchange={(g) => update({ goal: g })} />
				{#if c.prefarming}<span class="muted">Pre-farming</span>{/if}
			</div>
			{#if saveError}<p class="error">{saveError}</p>{/if}
		</div>
	</header>

	{#if c.goal === 'build' && c.targets}
		<section class="panel">
			<h2>Build targets</h2>
			<TargetsEditor targets={c.targets} levelCaps={caps} onchange={(t) => update({ targets: t })} />
			<label class="weapon-pick">
				<span>Planned weapon</span>
				<select aria-label="Planned weapon" value={c.planned_weapon_id ?? ''}
					onchange={(e) => setPlannedWeapon(e.currentTarget.value)}>
					<option value="">{c.owned && c.weapon ? `Equipped: ${c.weapon.name}` : 'None'}</option>
					{#each weapons as w (w.id)}<option value={w.id}>{'★'.repeat(w.rarity)} {w.name}</option>{/each}
				</select>
			</label>
		</section>
	{/if}

	{#if c.owned}
		<section class="panel">
			<h2>Current</h2>
			<p>Lv {c.level} · C{c.constellation} · Friendship {c.friendship}</p>
			{#if c.talents}
				<p>
					Talents {c.talents.normal}/{c.talents.skill}/{c.talents.burst}
					{#if c.targets && c.goal === 'build'}
						→ {c.targets.normal}/{c.targets.skill}/{c.targets.burst}{/if}
				</p>
			{/if}
			{#if c.weapon}
				<div class="weapon">
					{#if imgSrc(c.weapon.icon)}<img src={imgSrc(c.weapon.icon)} alt="" />{/if}
					<div>
						<b>{c.weapon.name}</b>
						<div class="muted">{'★'.repeat(c.weapon.rarity)} · Lv {c.weapon.level} · R{c.weapon.refinement}</div>
					</div>
				</div>
			{/if}
		</section>

		<section class="panel">
			<h2>Artifacts</h2>
			<div class="artifacts">
				{#each c.artifacts as a (a.slot)}
					<div class="artifact">
						<div class="muted">{SLOTS[a.slot] ?? `Slot ${a.slot}`} · +{a.level}</div>
						<b>{a.set_name}</b>
						<div>{a.main_stat}</div>
						<ul>{#each a.substats as s (s)}<li>{s}</li>{/each}</ul>
					</div>
				{:else}
					<p class="muted">No artifact data yet.</p>
				{/each}
			</div>
		</section>

		<section class="panel">
			<h2>Stats</h2>
			<table>
				<tbody>
					{#each c.stats as s (s.name)}<tr><td>{s.name}</td><td>{s.value}</td></tr>{/each}
				</tbody>
			</table>
		</section>
	{/if}

	{#if c.shortfall}
		<section class="panel" data-testid="shortfall">
			<h2>Material shortfall</h2>
			<p class="muted">{gapLabel(c.shortfall.gaps, now)}</p>
			{#if c.shortfall.gaps.skipped.includes(c.name)}
				<p class="muted">{c.name} planning isn't supported yet.</p>
			{:else if c.shortfall.materials.length === 0}
				<p class="muted">
					{c.shortfall.calculated ? 'Everything in the bag ✓' : notCalculatedLabel(c.shortfall.gaps, now)}
				</p>
			{:else}
				{#each groupByCategory(c.shortfall.materials) as group (group.key)}
					<h3 class="category">{group.label}</h3>
					<div class="tiles-row">
						{#each group.materials as m (m.id)}
							<MaterialTile name={m.name} icon={m.icon} rarity={m.rarity} view={charTileView(m)} testid="short-{m.id}" />
						{/each}
					</div>
				{/each}
			{/if}
		</section>
	{/if}
{/if}

<style>
	.hero { display: flex; gap: 20px; align-items: center; margin: 12px 0 16px; }
	.hero img { width: 420px; max-width: 50vw; height: 210px; object-fit: cover; border-radius: 10px; background: var(--r0); }
	.r5 img { background: var(--r5); }
	.r4 img { background: var(--r4); }
	.goal { margin-top: 10px; display: flex; gap: 10px; align-items: center; }
	section { margin-bottom: 12px; }
	.weapon { display: flex; gap: 10px; align-items: center; }
	.weapon img { width: 56px; height: 56px; }
	.artifacts { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 10px; }
	.artifact { background: var(--panel-2); border-radius: 8px; padding: 8px; }
	.artifact ul { margin: 4px 0 0; padding-left: 16px; color: var(--muted); }
	.tiles-row { display: flex; flex-wrap: wrap; gap: 10px; }
	h3.category { margin: 12px 0 6px; font-size: 0.85rem; font-weight: 600; color: var(--muted); }
	.weapon-pick { display: inline-flex; flex-direction: column; gap: 4px; margin-top: 12px; }
	table td { padding: 2px 16px 2px 0; }
</style>
