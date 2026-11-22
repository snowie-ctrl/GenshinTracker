<script lang="ts">
	import { onMount } from 'svelte';
	import { api, errorMessage } from '$lib/api';
	import Countdown from '$lib/Countdown.svelte';
	import { imgSrc } from '$lib/img';
	import { sync } from '$lib/sync.svelte';
	import { timeAgo } from '$lib/time';
	import type { ChallengeRunView, ProfileResponse } from '$lib/types';

	let data = $state<ProfileResponse | null>(null);
	let error = $state<string | null>(null);
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

	function result(kind: string, r: ChallengeRunView): string {
		const s = r.summary;
		if (kind === 'abyss') return `${s.stars ?? '—'}★ · floor ${s.max_floor ?? '—'} · ${s.wins ?? 0}/${s.battles ?? 0} wins`;
		if (kind === 'theater') return `Act ${s.act ?? '—'} · difficulty ${s.difficulty ?? '—'} · ${s.medals ?? 0} medals`;
		return `Difficulty ${s.difficulty ?? '—'}${s.time_used ? ` · ${s.time_used}s` : ''}`;
	}
</script>

<h1>Profile</h1>
{#if error}<p class="error">{error}</p>{/if}

{#if data}
	{#if data.profile}
		<p class="muted">as of {data.fetched_at ? timeAgo(data.fetched_at, now) : '—'}{#if data.error} · ⚠ last update failed: {data.error}{/if}</p>
		<section class="panel">
			<h2>AR {data.profile.ar} <span class="muted">· {data.profile.days_active} days active</span></h2>
			<div class="tiles">
				{#each [...data.profile.tiles, ...data.profile.chests, ...data.profile.oculi] as t, i (i)}
					<div class="tile"><div class="big">{t.value}</div><div class="muted">{t.label}</div></div>
				{/each}
			</div>
		</section>
		<section class="panel">
			<h2>Exploration</h2>
			<div class="regions">
				{#each data.profile.regions as r (r.id)}
					<div class="region">
						<div class="title">{r.name}</div>
						<div class="big">{r.explored}%</div>
						{#if r.reputation !== null}<div class="muted">Reputation {r.reputation}</div>{/if}
						{#each r.offerings as o, j (j)}<div class="muted">{o.name} {o.level}</div>{/each}
					</div>
				{/each}
			</div>
		</section>
	{:else}
		<p class="muted">{data.connected ? 'Sync to load your profile' : 'Connect HoYoLAB in Settings to load your profile'}</p>
	{/if}

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
					<tbody>
						{#each view.past as r (r.season)}
							<tr><td>{r.start?.slice(0, 10) ?? r.season}</td><td>{result(k.key, r)}</td></tr>
						{/each}
					</tbody>
				</table>
			{/if}
		</section>
	{/each}
{/if}

<style>
	section { margin-bottom: 12px; }
	.tiles, .regions { display: flex; flex-wrap: wrap; gap: 10px; }
	.tile, .region { background: var(--panel-2); border-radius: 10px; padding: 8px 12px; min-width: 110px; }
	.big { font-size: 20px; font-weight: 600; }
	.team img { width: 36px; height: 36px; border-radius: 50%; }
	.initial { width: 36px; height: 36px; border-radius: 50%; background: var(--panel-2); display: inline-flex;
		align-items: center; justify-content: center; font-weight: 600; }
	.team { display: flex; gap: 4px; margin: 4px 0; }
</style>
