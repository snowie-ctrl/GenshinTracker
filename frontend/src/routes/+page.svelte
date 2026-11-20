<script lang="ts">
	import { onMount } from 'svelte';
	import { api, errorMessage } from '$lib/api';
	import { imgSrc } from '$lib/img';
	import { sync } from '$lib/sync.svelte';
	import { formatDuration, timeAgo } from '$lib/time';
	import type { Dashboard } from '$lib/types';

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
{/if}

<style>
	.tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; margin-bottom: 12px; }
	.big { font-size: 28px; font-weight: 700; }
	.big .muted { font-size: 16px; font-weight: 400; }
	.expeditions { display: flex; flex-wrap: wrap; gap: 12px; }
	.exp { display: flex; align-items: center; gap: 6px; }
	.exp img { width: 36px; height: 36px; border-radius: 50%; background: var(--panel-2); }
</style>
