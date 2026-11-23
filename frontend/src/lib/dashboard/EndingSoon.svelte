<script lang="ts">
	import Countdown from '$lib/Countdown.svelte';
	import { topReward } from '$lib/dashboard';
	import { imgSrc } from '$lib/img';
	import type { EventRow } from '$lib/types';
	let { events, now }: { events: EventRow[]; now: number } = $props();
</script>

{#if events.length > 0}
	<section class="panel strip" data-testid="ending-soon">
		<h2>Ending soon</h2>
		<ul>
			{#each events as e (e.id)}
				{@const r = topReward(e.rewards)}
				<li>{#if r && imgSrc(r.icon)}<img src={imgSrc(r.icon)} alt="" />{/if}<a href="/events">{e.name}</a> <Countdown at={e.end} {now} warn /></li>
			{/each}
		</ul>
	</section>
{/if}

<style>
	.strip { border-color: var(--warn); }
	ul { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 8px 20px; }
	li { display: inline-flex; gap: 8px; align-items: center; }
	img { width: 28px; height: 28px; }
	h2 { margin-top: 0; }
</style>
