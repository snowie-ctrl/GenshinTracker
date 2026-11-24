<!-- frontend/src/routes/profile/+page.svelte -->
<script lang="ts">
	import { onMount } from 'svelte';
	import { api, errorMessage } from '$lib/api';
	import { WEAPON_TYPES } from '$lib/charts';
	import Countdown from '$lib/Countdown.svelte';
	import { ELEMENT_STYLE } from '$lib/elements';
	import Icon from '$lib/Icon.svelte';
	import { imgSrc } from '$lib/img';
	import ProfileHeader from '$lib/ProfileHeader.svelte';
	import { TILE_ICON, tileTitle, topBosses } from '$lib/profile';
	import RadarChart from '$lib/RadarChart.svelte';
	import RegionCard from '$lib/RegionCard.svelte';
	import Showcase from '$lib/Showcase.svelte';
	import { sync } from '$lib/sync.svelte';
	import type { ChallengeRunView, ProfileResponse } from '$lib/types';

	let data = $state<ProfileResponse | null>(null);
	let error = $state<string | null>(null);
	let toast = $state<string | null>(null);
	let allBosses = $state(false);
	let now = $state(Date.now());
	const KINDS = [
		{ key: 'abyss', title: 'Spiral Abyss' },
		{ key: 'theater', title: 'Imaginarium Theater' },
		{ key: 'stygian', title: 'Stygian Onslaught' }
	] as const;

	$effect(() => {
		void sync.version;
		api.profile().then((d) => { data = d; error = null; }).catch((e) => (error = errorMessage(e)));
	});

	onMount(() => {
		const t = setInterval(() => (now = Date.now()), 30_000);
		return () => clearInterval(t);
	});

	async function saveShowcase(ids: number[]) {
		if (!data) return;
		try {
			const r = await api.setShowcase(ids);
			data = { ...data, showcase: r.showcase, showcase_mode: r.showcase_mode };
			toast = null;
		} catch (e) {
			toast = errorMessage(e);
		}
	}

	function result(kind: string, r: ChallengeRunView): string {
		const s = r.summary;
		if (kind === 'abyss') return `${s.stars ?? '—'}★ · floor ${s.max_floor ?? '—'} · ${s.wins ?? 0}/${s.battles ?? 0} wins`;
		if (kind === 'theater') return `Act ${s.act ?? '—'} · difficulty ${s.difficulty ?? '—'} · ${s.medals ?? 0} medals`;
		return `Difficulty ${s.difficulty ?? '—'}${s.time_used ? ` · ${s.time_used}s` : ''}`;
	}
</script>

{#if error}<p class="error">{error}</p>{/if}
{#if toast}<p class="error" role="alert">{toast}</p>{/if}

{#if data}
	{#if data.profile}
		<ProfileHeader header={data.profile.header} portrait={data.showcase[0]?.icon ?? null}
			fetchedAt={data.fetched_at} error={data.error} {now} />
	{:else}
		<h1>Profile</h1>
		<p class="muted">{data.connected ? 'Sync to load your profile' : 'Connect HoYoLAB in Settings to load your profile'}</p>
	{/if}

	{#if data.owned.length}
		<Showcase entries={data.showcase} mode={data.showcase_mode} owned={data.owned} onsave={saveShowcase} />
	{/if}

	{#if data.profile}
		<section class="panel tiles" data-testid="stat-tiles">
			{#each data.profile.tiles as t (t.key)}
				<div class="tile" title={tileTitle(t) || undefined}>
					<span class="ic"><Icon name={TILE_ICON[t.key] ?? 'profile'} size={20} /></span>
					<span class="v">{typeof t.value === 'number' ? t.value.toLocaleString() : t.value}</span>
					<span class="muted small">{t.label}</span>
				</div>
			{/each}
		</section>

		<section class="panel">
			<h2>Exploration</h2>
			<div class="regions">
				{#each data.profile.regions as r (r.id)}<RegionCard region={r} />{/each}
			</div>
		</section>
	{/if}

	<div class="three">
		<section class="panel" data-testid="roster">
			<h2>Roster <span class="muted small">{data.roster.total} characters</span></h2>
			<ul class="bars">
				{#each Object.entries(data.roster.elements) as [el, n] (el)}
					<li><span>{el}</span><span class="bar"><span style="width: {data.roster.total ? (n / data.roster.total) * 100 : 0}%; background: {ELEMENT_STYLE[el]?.color ?? 'var(--muted)'}"></span></span><span>{n}</span></li>
				{/each}
			</ul>
			<RadarChart title="Weapon types" size={160} axes={WEAPON_TYPES.map((w) => ({ label: w }))}
				series={[{ name: 'Owned', values: WEAPON_TYPES.map((w) => data?.roster.weapon_types[w] ?? 0), color: 'var(--avg-pity)' }]} />
			<div class="muted small">5★ {data.roster.rarity['5']} · 4★ {data.roster.rarity['4']} · {data.roster.constellations} constellations · {data.roster.c6} at C6</div>
		</section>

		{#if data.profile?.teapot}
			{@const tp = data.profile.teapot}
			<section class="panel" data-testid="teapot">
				<h2><Icon name="teapot" size={18} /> Serenitea Pot</h2>
				<div class="big">Lv {tp.level}</div>
				<div>{#if imgSrc(tp.comfort_icon)}<img class="sm" src={imgSrc(tp.comfort_icon)} alt="" />{/if}{tp.comfort.toLocaleString()} comfort · {tp.comfort_name}</div>
				<div class="muted small">{tp.items.toLocaleString()} furnishings · {tp.visitors} visitors</div>
				<div class="realms">{#each tp.realms as r, i (i)}{#if imgSrc(r.icon)}<img src={imgSrc(r.icon)} alt={r.name} title={r.name} />{:else}<span class="muted small">{r.name}</span>{/if}{/each}</div>
			</section>
		{/if}

		{#if data.profile?.bosses.length}
			<section class="panel" data-testid="bosses">
				<h2><Icon name="boss" size={18} /> Boss kills</h2>
				<ol class="bosses">
					{#each topBosses(data.profile.bosses, allBosses) as b (b.name)}<li><span>{b.name}</span><strong>{b.kills}</strong></li>{/each}
				</ol>
				{#if data.profile.bosses.length > 6}
					<button type="button" onclick={() => (allBosses = !allBosses)}>{allBosses ? 'Show fewer' : `Show all ${data.profile.bosses.length}`}</button>
				{/if}
			</section>
		{/if}
	</div>

	<div class="three">
		{#each KINDS as k (k.key)}
			{@const view = data.challenges[k.key]}
			<section class="panel">
				<h2>{k.title}</h2>
				<div data-testid="{k.key}-current">
					{#if view.current}
						<p>{result(k.key, view.current)} · ends in <Countdown at={view.current.end} {now} /></p>
						{#each view.current.teams as team, i (i)}
							<div class="team">{#each team as c (c.id)}{#if imgSrc(c.icon)}<img src={imgSrc(c.icon)} alt={c.name} title={c.name} />{:else}<span class="initial" title={c.name}>{c.name.slice(0, 1)}</span>{/if}{/each}</div>
						{/each}
					{:else}
						<p class="muted">Not attempted this cycle</p>
					{/if}
				</div>
				{#if view.past.length}
					<h3>Past runs</h3>
					<table data-testid="{k.key}-past">
						<thead><tr><th>Started</th><th>Result</th></tr></thead>
						<tbody>
							{#each view.past as r (r.season)}
								<tr><td>{r.start?.slice(0, 10) ?? r.season}</td><td>{result(k.key, r)}</td></tr>
							{/each}
						</tbody>
					</table>
				{/if}
			</section>
		{/each}
	</div>
{/if}

<style>
	section.panel { margin-bottom: 12px; }
	.tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 10px; }
	.tile { background: var(--panel-2); border-radius: 10px; padding: 8px 12px; display: grid; grid-template-columns: auto 1fr; column-gap: 8px; align-items: center; }
	.tile .ic { grid-row: span 2; color: var(--avg-pity); }
	.tile .v { font-size: 18px; font-weight: 700; }
	.regions { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px; }
	.three { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
	@media (max-width: 900px) { .three { grid-template-columns: 1fr; } }
	.three section.panel { margin-bottom: 0; }
	.three + .three { margin-top: 12px; }
	h2 { display: flex; align-items: center; gap: 6px; }
	.bars { list-style: none; padding: 0; margin: 0 0 8px; display: grid; gap: 3px; font-size: 12px; }
	.bars li { display: grid; grid-template-columns: 64px 1fr 24px; gap: 6px; align-items: center; }
	.bar { height: 7px; background: var(--line); border-radius: 4px; overflow: hidden; }
	.bar span { display: block; height: 100%; }
	.big { font-size: 22px; font-weight: 700; }
	.sm { width: 18px; height: 18px; vertical-align: -4px; margin-right: 4px; }
	.realms { display: flex; gap: 4px; margin-top: 6px; }
	.realms img { width: 28px; height: 28px; border-radius: 6px; }
	.bosses { padding-left: 18px; margin: 0 0 6px; display: grid; gap: 2px; font-size: 13px; }
	.bosses li span { display: inline-block; min-width: 70%; }
	.small { font-size: 12px; }
	.team img { width: 36px; height: 36px; border-radius: 50%; }
	.initial { width: 36px; height: 36px; border-radius: 50%; background: var(--panel-2); display: inline-flex;
		align-items: center; justify-content: center; font-weight: 600; }
	.team { display: flex; gap: 4px; margin: 4px 0; }
	th { text-align: left; font-size: 12px; color: var(--muted); font-weight: 500; padding-right: 14px; }
</style>
