<script lang="ts">
	import { onMount } from 'svelte';
	import { api, errorMessage } from '$lib/api';
	import ArtifactDomains from '$lib/dashboard/ArtifactDomains.svelte';
	import BuildList from '$lib/dashboard/BuildList.svelte';
	import CompletedBuilds from '$lib/dashboard/CompletedBuilds.svelte';
	import DomainDays from '$lib/dashboard/DomainDays.svelte';
	import EndingSoon from '$lib/dashboard/EndingSoon.svelte';
	import EventList from '$lib/dashboard/EventList.svelte';
	import Greeting from '$lib/dashboard/Greeting.svelte';
	import LiveBanners from '$lib/dashboard/LiveBanners.svelte';
	import NoteBubbles from '$lib/dashboard/NoteBubbles.svelte';
	import TimerList from '$lib/dashboard/TimerList.svelte';
	import WeeklyBosses from '$lib/dashboard/WeeklyBosses.svelte';
	import { gapLabel, shouldPoll } from '$lib/materials';
	import { sync } from '$lib/sync.svelte';
	import { timeAgo } from '$lib/time';
	import type { Dashboard, PriorityResult } from '$lib/types';

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

	let loadSeq = 0;
	async function load() {
		const seq = ++loadSeq;
		try {
			const d = await api.dashboard();
			if (seq !== loadSeq) return;   // a newer load is in flight or done
			data = d;
			error = null;
		} catch (e) {
			if (seq === loadSeq) error = errorMessage(e);
		}
	}

	$effect(() => {
		if (!shouldPoll(data?.gaps)) return;
		const t = setTimeout(load, 2000);
		return () => clearTimeout(t);
	});

	function saved(r: PriorityResult) {
		loadSeq++;   // drop any older load still in flight; it would overwrite this order
		if (data) data = { ...data, builds: r.builds, completed: r.completed };
		void load();   // domain and boss cards re-rank by the new priority
	}
</script>

{#if error}<p class="error">{error}</p>{/if}
{#if data}
	<div class="dash">
		<div class="centre">
			<Greeting name={data.display_name} {now} />
			<NoteBubbles notes={data.notes} connection={data.connection} {now} />
			<p class="muted small">{#if data.notes}As of {timeAgo(data.notes.fetched_at, now)} · {/if}{gapLabel(data.gaps, now)}</p>
			<EndingSoon events={data.ending_soon} {now} />
			<DomainDays days={data.domains_by_day} today={data.server_weekday}
				hasBuilds={data.builds.length + data.completed.length > 0} gaps={data.gaps} {now} />
			<WeeklyBosses weekly={data.weekly_bosses} hasBuilds={data.builds.length + data.completed.length > 0}
				gaps={data.gaps} {now} />
			<ArtifactDomains view={data.artifact_domains} />
			<BuildList builds={data.builds} completedCount={data.completed.length} gaps={data.gaps} {now} onsaved={saved} />
			<CompletedBuilds completed={data.completed} />
		</div>
		<aside class="side">
			<TimerList timers={data.timers} {now} />
			<LiveBanners banners={data.live_banners} fetchedAt={data.calendar_fetched_at} {now} />
			<EventList events={data.events} fetchedAt={data.calendar_fetched_at} {now} onchanged={load} />
		</aside>
	</div>
{/if}

<style>
	.dash { display: grid; grid-template-columns: minmax(0, 2fr) minmax(280px, 1fr); gap: 16px; align-items: start; }
	.centre, .side { display: grid; gap: 12px; min-width: 0; }
	.small { font-size: 12px; margin: 0; }
	@media (max-width: 1100px) { .dash { grid-template-columns: minmax(0, 1fr); } }
</style>
