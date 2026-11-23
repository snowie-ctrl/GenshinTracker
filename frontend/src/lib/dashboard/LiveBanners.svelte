<script lang="ts">
	import Countdown from '$lib/Countdown.svelte';
	import { bannerPity } from '$lib/dashboard';
	import { imgSrc } from '$lib/img';
	import type { DashBanner } from '$lib/types';
	let { banners, fetchedAt, now }: { banners: DashBanner[]; fetchedAt: string | null; now: number } = $props();
</script>

<section class="panel" data-testid="dash-banners">
	<h2><a href="/events">Live banners</a></h2>
	{#if banners.length === 0}
		<p class="muted">{fetchedAt ? 'No live banners.' : 'Sync to load events'}</p>
	{:else}
		<ul>
			{#each banners as b (b.id)}
				{@const five = b.items.find((i) => i.rarity === 5)}
				<li>
					{#if five && imgSrc(five.icon)}<img src={imgSrc(five.icon)} alt={five.name} />{/if}
					<div><div>{b.name}</div>
						<div class="muted small">Ends <Countdown at={b.end} {now} warn />{#if bannerPity(b.pity)} · {bannerPity(b.pity)}{/if}</div></div>
				</li>
			{/each}
		</ul>
	{/if}
</section>

<style>
	ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
	li { display: flex; gap: 10px; align-items: center; }
	img { width: 40px; height: 40px; border-radius: 50%; background: var(--r5); }
	.small { font-size: 12px; }
</style>
