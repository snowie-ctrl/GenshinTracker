<script lang="ts">
	import { onMount } from 'svelte';
	import { api, errorMessage } from '$lib/api';
	import { imgSrc } from '$lib/img';
	import { sync } from '$lib/sync.svelte';
	import { formatDuration, timeAgo } from '$lib/time';
	import type { Dashboard } from '$lib/types';
	import { pityLine } from '$lib/wishes';
	import { teamTileView } from '$lib/teams';
	import MaterialPopover from '$lib/MaterialPopover.svelte';
	import MaterialTile from '$lib/MaterialTile.svelte';
	import {
		charTileView, gapLabel, gapsSettled, notCalculatedLabel, shouldPoll, tileView, weekdayNames
	} from '$lib/materials';
	import type { WeeklyBoss } from '$lib/types';

	let toast = $state<string | null>(null);
	let data = $state<Dashboard | null>(null);
	let error = $state<string | null>(null);
	let now = $state(Date.now());

	$effect(() => {
		void sync.version;
		load();
	});

	onMount(() => {
		const t = setInterval(() => (now = Date.now()), 1000);
		return () => clearInterval(t);
	});

	async function load() {
		try {
			data = await api.dashboard();
			error = null;
		} catch (e) {
			error = errorMessage(e);
		}
	}

	$effect(() => {
		if (!shouldPoll(data?.gaps)) return;
		const t = setTimeout(load, 2000);
		return () => clearTimeout(t);
	});

	const bosses = $derived([...(data?.weekly_bosses.bosses ?? [])].sort((a, b) => Number(a.done) - Number(b.done)));

	async function toggleBoss(b: WeeklyBoss) {
		const done = !b.done;
		b.done = done;
		try {
			await api.setBossDone(b.name, done);
			toast = null;
		} catch (e) {
			b.done = !done;
			toast = errorMessage(e);
		}
	}

	const notes = $derived(data?.notes ?? null);
	const resinFullIn = $derived(notes ? Date.parse(notes.resin_full_at) - now : 0);
</script>

<h1>Dashboard</h1>
{#if error}<p class="error">{error}</p>{/if}

{#if data}
	{#if data.connection.status === 'missing'}
		<section class="panel">Connect HoYoLAB in <a href="/settings">Settings</a> to see your account here.</section>
	{/if}

	<div class="tiles">
		<section class="panel tile" data-testid="resin">
			<h2>Original Resin</h2>
			{#if notes}
				<div class="big">{notes.resin}<span class="muted">/{notes.resin_max}</span></div>
				<div class="muted">{resinFullIn <= 0 ? 'Full' : `Full in ${formatDuration(resinFullIn)}`}</div>
			{:else}<div class="muted">No data yet</div>{/if}
		</section>
		<section class="panel tile">
			<h2>Commissions</h2>
			{#if notes}<div class="big">{notes.commissions_done}<span class="muted">/{notes.commissions_max}</span></div>
			{:else}<div class="muted">No data yet</div>{/if}
		</section>
		<section class="panel tile">
			<h2>Realm Currency</h2>
			{#if notes}<div class="big">{notes.realm_currency}<span class="muted">/{notes.realm_currency_max}</span></div>
			{:else}<div class="muted">No data yet</div>{/if}
		</section>
		<section class="panel tile">
			<h2>Building</h2>
			<div class="big">{data.building.count}</div>
			<div class="muted">
				{data.building.average_progress === null
					? 'Nothing set to Build yet'
					: `Average ${Math.round(data.building.average_progress * 100)}% to target`}
			</div>
			<a href="/characters">Characters →</a>
		</section>
	</div>

	<section class="panel" data-testid="pity-card">
		<h2>Pity</h2>
		{#if data.pity.length === 0}
			<p class="muted"><a href="/wishes">Import your wish history</a></p>
		{:else}
			<ul class="pity-lines">
				{#each data.pity as line (line.pool)}
					<li><a href="/wishes">{pityLine(line)}</a></li>
				{/each}
			</ul>
		{/if}
	</section>

	<section class="panel" data-testid="build-teams">
		<h2>Build teams</h2>
		{#if data.build_teams.length === 0}
			<p class="muted"><a href="/teams">Tag a team Build to plan it here</a></p>
		{:else}
			{#each data.build_teams as t (t.id)}
				<div class="team-row">
					<a class="title" href="/teams#team-{t.id}">{t.name}</a>
					<span class="avatars">
						{#each t.members as m (m.id)}
							{#if m.slug}
								<a href="/characters/{m.slug}" title={m.name}>{#if imgSrc(m.icon)}<img src={imgSrc(m.icon)} alt={m.name} />{/if}</a>
							{:else if imgSrc(m.icon)}
								<img src={imgSrc(m.icon)} alt={m.name} title={m.name} />
							{/if}
						{/each}
					</span>
					{#if t.progress !== null}<span class="muted">{Math.round(t.progress * 100)}%</span>{/if}
					<span class="tiles-row">
						{#each t.top as m (m.id)}
							<MaterialTile name={m.name} icon={m.icon} rarity={m.rarity} view={teamTileView(m)} />
						{/each}
					</span>
					{#if t.more > 0}<a href="/teams#team-{t.id}">+{t.more} more</a>{/if}
					{#if t.has_shortfall && t.top.length === 0}
							{#if t.all_calculated && t.short_count === 0 && data.connection.status === 'connected' && !data.gaps.stale && gapsSettled(data.gaps)}
								<span class="ok">Everything in the bag ✓</span>
							{:else if data.gaps.stale || data.gaps.pending}
								<span class="muted">Updating…</span>
							{:else if t.short_count > 0 && t.all_calculated}
								<span class="muted">Everything left is craftable from your bag</span>
							{:else}
								<span class="muted">{notCalculatedLabel(data.gaps, now)}</span>
							{/if}
						{/if}
				</div>
			{/each}
		{/if}
	</section>

	{#if notes}
		<section class="panel">
			<h2>Expeditions</h2>
			<div class="expeditions">
				{#each notes.expeditions as e, i (i)}
					<div class="exp">
						{#if imgSrc(e.icon)}<img src={imgSrc(e.icon)} alt="" />{/if}
						<span>
							{e.finished || Date.parse(e.return_at) <= now
								? 'Done'
								: `Back in ${formatDuration(Date.parse(e.return_at) - now)}`}
						</span>
					</div>
				{:else}
					<span class="muted">No expeditions running.</span>
				{/each}
			</div>
		</section>
		<p class="muted">As of {timeAgo(notes.fetched_at, now)}.</p>
	{/if}

	{#if toast}<p class="error">{toast}</p>{/if}
	<p class="muted">{gapLabel(data.gaps, now)}</p>

	<section class="panel" data-testid="farm-today">
		<h2>Active today</h2>
		{#if data.building_cards.length === 0}
			<p class="muted">Set characters to Build to plan farming.</p>
		{:else if data.farm_today.domains.length === 0}
			<p class="muted">
				{gapsSettled(data.gaps) ? 'Nothing to farm in domains today ✓' : notCalculatedLabel(data.gaps, now)}
			</p>
		{:else}
			<div class="cards">
				{#each data.farm_today.domains as d (d.id)}
					<div class="card">
						<div class="title">{d.name}</div>
						<div class="muted small">{weekdayNames(d.weekdays)}</div>
						<div class="tiles-row">
							{#each d.materials as m (m.id)}
								<MaterialTile name={m.name} icon={m.icon} rarity={m.rarity} view={tileView(m)}>
									{#snippet popover()}<MaterialPopover material={m} />{/snippet}
								</MaterialTile>
							{/each}
						</div>
						<div class="avatars">
							{#each d.characters as c (c.id)}
								<a href="/characters/{c.slug}" title={c.name}>{#if imgSrc(c.icon)}<img src={imgSrc(c.icon)} alt={c.name} />{/if}</a>
							{/each}
						</div>
					</div>
				{/each}
			</div>
		{/if}
	</section>

	<section class="panel">
		<h2>Weekly bosses</h2>
		{#if data.weekly_bosses.discounts_left !== null}
			<p class="muted">Discounted runs left {data.weekly_bosses.discounts_left}/{data.weekly_bosses.discounts_max}</p>
		{/if}
		{#if data.building_cards.length === 0}
			<p class="muted">Set characters to Build to plan farming.</p>
		{:else if bosses.length === 0}
			<p class="muted">
				{gapsSettled(data.gaps) ? 'No weekly boss drops to farm ✓' : notCalculatedLabel(data.gaps, now)}
			</p>
		{:else}
			<div class="cards">
				{#each bosses as b (b.name)}
					<div class="card" class:done={b.done} data-testid="boss-{b.name}">
						<label class="title">
							<input type="checkbox" checked={b.done} onchange={() => toggleBoss(b)} aria-label="Done this week" />
							{b.name}
						</label>
						<div class="tiles-row">
							{#each b.materials as m (m.id)}
								<MaterialTile name={m.name} icon={m.icon} rarity={m.rarity} view={tileView(m)}>
									{#snippet popover()}<MaterialPopover material={m} />{/snippet}
								</MaterialTile>
							{/each}
						</div>
						<div class="avatars">
							{#each b.characters as c (c.id)}
								<a href="/characters/{c.slug}" title={c.name}>{#if imgSrc(c.icon)}<img src={imgSrc(c.icon)} alt={c.name} />{/if}</a>
							{/each}
						</div>
					</div>
				{/each}
			</div>
		{/if}
	</section>

	<section class="panel">
		<h2>Building</h2>
		{#if data.building_cards.length === 0}
			<p class="muted">Set characters to Build to plan farming.</p>
		{/if}
		<div class="cards">
			{#each data.building_cards as card (card.character.id)}
				<div class="card build" data-testid="building-card-{card.character.slug}">
					<div class="head">
						{#if imgSrc(card.character.icon)}<img src={imgSrc(card.character.icon)} alt="" />{/if}
						<div>
							<a class="title" href="/characters/{card.character.slug}">{card.character.name}</a>
							{#if card.progress !== null}
								<div class="bar" role="progressbar" aria-valuenow={Math.round(card.progress * 100)}
									aria-valuemin={0} aria-valuemax={100}><span style="width: {card.progress * 100}%"></span></div>
							{/if}
						</div>
					</div>
					{#if card.skipped}
						<p class="muted">{card.character.name} planning isn't supported yet.</p>
					{:else if card.materials.length === 0}
						<p class="muted">
							{card.calculated ? 'Everything in the bag ✓' : notCalculatedLabel(data.gaps, now)}
						</p>
					{:else}
						<div class="tiles-row">
							{#each card.materials as m (m.id)}
								<MaterialTile name={m.name} icon={m.icon} rarity={m.rarity} view={charTileView(m)} />
							{/each}
						</div>
					{/if}
				</div>
			{/each}
		</div>
	</section>
{/if}

<style>
	.cards { display: flex; flex-wrap: wrap; gap: 12px; }
	.card { background: var(--panel-2); border: 1px solid var(--line); border-radius: 10px; padding: 10px;
		min-width: 220px; color: inherit; text-decoration: none; }
	.card.done { opacity: 0.45; }
	.card .title { font-weight: 600; display: flex; gap: 6px; align-items: center; }
	.small { font-size: 12px; }
	.tiles-row { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0; }
	.avatars { display: flex; gap: 4px; }
	.avatars img { width: 28px; height: 28px; border-radius: 50%; background: var(--r0); }
	.card.build .head { display: flex; gap: 8px; align-items: center; }
	.card.build .head img { width: 40px; height: 40px; border-radius: 8px; background: var(--r0); }
	.bar { width: 140px; height: 6px; background: var(--line); border-radius: 3px; overflow: hidden; }
	.bar span { display: block; height: 100%; background: var(--building); }
	section.panel { margin-top: 12px; }
	.tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; margin-bottom: 12px; }
	.pity-lines { list-style: none; padding: 0; margin: 0; display: flex; flex-wrap: wrap; gap: 6px 18px; }
	.team-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; padding: 6px 0; border-bottom: 1px solid var(--line); }
	.team-row:last-child { border-bottom: none; }
	.team-row .avatars img { width: 32px; height: 32px; border-radius: 50%; }
	.ok { color: var(--accent); }
	.big { font-size: 28px; font-weight: 700; }
	.big .muted { font-size: 16px; font-weight: 400; }
	.expeditions { display: flex; flex-wrap: wrap; gap: 12px; }
	.exp { display: flex; align-items: center; gap: 6px; }
	.exp img { width: 36px; height: 36px; border-radius: 50%; background: var(--panel-2); }
</style>
