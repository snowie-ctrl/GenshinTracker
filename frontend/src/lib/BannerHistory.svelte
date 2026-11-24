<script lang="ts">
	import { untrack } from 'svelte';
	import { api, errorMessage } from './api';
	import { cssUrl, imgSrc } from './img';
	import type { HistoryPhase, HistoryVersion } from './types';

	let q = $state('');
	let query = $state('');
	let versions = $state<HistoryVersion[]>([]);
	let page = $state(0);
	let total = $state(0);
	let loading = $state(false);
	let toast = $state<string | null>(null);
	let failed = $state(false);
	let sentinel = $state<HTMLDivElement>();
	let request = 0;
	const more = $derived(versions.length < total);

	$effect(() => {
		const typed = q;
		const timer = setTimeout(() => { if (typed !== query) query = typed; }, 250);
		return () => clearTimeout(timer);
	});

	$effect(() => {
		void query;
		versions = [];
		failed = false;
		page = 0;
		total = 0;
		const forQuery = query;
		untrack(() => loadNext(forQuery));
	});

	$effect(() => {
		if (!sentinel) return;
		const io = new IntersectionObserver((entries) => {
			if (entries.some((e) => e.isIntersecting) && more && !loading) loadNext(query);
		}, { rootMargin: '200px' });
		io.observe(sentinel);
		return () => io.disconnect();
	});

	async function loadNext(forQuery: string) {
		const mine = ++request;
		loading = true;
		try {
			const res = await api.bannerHistory(forQuery, page + 1);
			if (mine !== request) return;
			toast = null;
			failed = false;
			versions = [...versions, ...res.versions];
			page = res.page;
			total = res.total_versions;
		} catch (e) {
			if (mine === request) failed = true;
			if (mine === request) toast = `Could not load banner history: ${errorMessage(e)}`;
		} finally {
			if (mine === request) loading = false;
		}
	}

	const day = (s: string) => new Date(s.replace(' ', 'T')).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
	const got = (p: HistoryPhase) => p.banners.flatMap((b) => b.pulls?.fives ?? []);
	const pulls = (p: HistoryPhase) => p.banners.reduce((n, b) => n + (b.pulls?.pulls ?? 0), 0);
</script>

<section class="panel" data-testid="banner-history">
	<h2>Banner history</h2>
	{#if toast && !(failed && versions.length === 0)}<div class="toast error">{toast} <button type="button" onclick={() => (toast = null)}>Dismiss</button></div>{/if}
	<input class="search" placeholder="Search banner or item" bind:value={q} aria-label="Search banners" />
	{#each versions as v (v.version)}
		<div class="version" data-testid="version-{v.version}">
			<div class="vlabel">{v.version}</div>
			<div class="phases">
				{#each v.phases as p, i (p.start)}
					<div class="phase" class:upcoming={p.upcoming} data-testid="phase">
						<h5>Phase {i + 1} · {day(p.start)} – {day(p.end)}{#if p.upcoming} <span class="tag">upcoming</span>{/if}</h5>
						{#if p.upcoming}
							{#if imgSrc(p.image)}<div class="strip" style="background-image:{cssUrl(imgSrc(p.image) ?? '')}, var(--grad)"></div>{/if}
							<div class="muted">{p.banners.map((b) => b.name).join(' · ')}</div>
						{:else}
							<div class="names muted">{p.banners.map((b) => b.name).join(' · ')}</div>
							<div class="five">
								{#each p.banners.filter((b) => b.pool !== 'weapon') as b (b.key)}
									{#each b.featured_5 as it (it.id)}{#if imgSrc(it.icon)}<img class="c r5" src={imgSrc(it.icon)} alt={it.name} title={it.name} />{/if}{/each}
								{/each}
								<span class="sep"></span>
								{#each p.banners.filter((b) => b.pool === 'weapon') as b (b.key)}
									{#each b.featured_5 as it (it.id)}{#if imgSrc(it.icon)}<img class="w r5" src={imgSrc(it.icon)} alt={it.name} title={it.name} />{/if}{/each}
								{/each}
							</div>
							<div class="four">
								{#each p.banners as b (b.key)}
									{#each b.featured_4 as it (it.id)}{#if imgSrc(it.icon)}<img class="r4" src={imgSrc(it.icon)} alt={it.name} title={it.name} />{/if}{/each}
								{/each}
							</div>
							{#if p.banners.some((b) => b.pool === 'chronicled')}<span class="tag">Chronicled</span>{/if}
							{#if pulls(p) > 0}<span class="you" class:got={got(p).length > 0}>{pulls(p)} pulls{#if got(p).length} · got {got(p).join(', ')}{/if}</span>{/if}
						{/if}
					</div>
				{/each}
			</div>
		</div>
	{:else}
		{#if failed && !loading}
			<p class="error">{toast ?? 'Could not load banner history.'} <button type="button" onclick={() => loadNext(query)}>Retry</button></p>
		{:else if !loading}<p class="muted">No banners match.</p>{/if}
	{/each}
	{#if more}
		<div bind:this={sentinel}></div>
		<button type="button" disabled={loading} onclick={() => loadNext(query)}>Load more</button>
	{/if}
</section>

<style>
	.search { margin-bottom: 10px; }
	.version { display: grid; grid-template-columns: 56px minmax(0, 1fr); gap: 10px; margin-bottom: 10px; }
	.vlabel { font-size: 20px; font-weight: 700; color: #e8cf9c; display: flex; align-items: center; justify-content: center; border-right: 1px solid var(--line); }
	.phases { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 10px; }
	.phase { background: var(--panel-2); border-radius: 10px; padding: 8px 10px; }
	.phase h5 { margin: 0 0 4px; font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: var(--muted); font-weight: 600; }
	.names { font-size: 12px; margin-bottom: 6px; }
	.five { display: flex; gap: 6px; align-items: flex-end; }
	.five img.c { width: 54px; height: 54px; border-radius: 8px; }
	.five img.w { width: 40px; height: 40px; border-radius: 8px; }
	.sep { width: 1px; align-self: stretch; background: var(--line); margin: 0 4px; }
	.four { display: flex; gap: 3px; margin-top: 5px; }
	.four img { width: 24px; height: 24px; border-radius: 5px; }
	.r5 { background: var(--r5); } .r4 { background: var(--r4); }
	.tag { font-size: 10px; padding: 1px 6px; border-radius: 999px; background: var(--panel); margin-right: 6px; }
	.you { display: inline-block; margin-top: 6px; padding: 1px 8px; border-radius: 999px; background: rgba(142, 197, 255, 0.18); font-size: 11px; }
	.you.got { background: rgba(232, 207, 156, 0.25); color: #f3d9a6; }
	.strip { --grad: linear-gradient(120deg, rgba(120, 130, 180, 0.35), rgba(60, 70, 110, 0.35)); height: 60px; border-radius: 8px; background-size: cover; background-position: center; margin-bottom: 6px; }
</style>
