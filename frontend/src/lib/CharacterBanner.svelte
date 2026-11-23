<script lang="ts">
	import { page } from '$app/state';
	import GoalSwitch from './GoalSwitch.svelte';
	import { elementStyle } from './elements';
	import { imgSrc } from './img';
	import type { CharacterDetail, Goal } from './types';

	let { c, onGoal }: { c: CharacterDetail; onGoal: (g: Goal) => void } = $props();

	const base = $derived(`/characters/${c.slug}`);
	const tabs = $derived([
		{ id: 'current', label: 'Current', href: base },
		{ id: 'build', label: 'Build', href: `${base}/build` },
		{ id: 'guide', label: 'Guide', href: `${base}/guide` }
	]);
	const el = $derived(elementStyle(c.element));
</script>

<header class="banner" data-testid="banner">
	{#if imgSrc(c.splash)}<img class="art" src={imgSrc(c.splash)} alt="" />{/if}
	<div class="fade"></div>
	<div class="text">
		<h1>{c.name}</h1>
		<div class="meta">
			<span class="stars">{'★'.repeat(c.rarity || 0)}</span>
			{#if el.icon && imgSrc(el.icon)}<img class="el" src={imgSrc(el.icon)} alt="" />{/if}
			<span>{c.element ?? '—'}</span><span>·</span><span>{c.weapon_type ?? '—'}</span>
		</div>
		<div class="goal">
			<GoalSwitch goal={c.goal} onchange={onGoal} />
			{#if c.prefarming}<span class="muted">Pre-farming</span>{/if}
			{#if c.goal === 'build' && c.priority}<a class="prio" href="/">Priority #{c.priority}</a>{/if}
		</div>
	</div>
	<nav class="tabs" aria-label="Character sections">
		{#each tabs as t (t.id)}
			<a href={t.href} data-testid="tab-{t.id}" aria-current={page.url.pathname === t.href ? 'page' : undefined}>{t.label}</a>
		{/each}
	</nav>
</header>

<style>
	.banner { position: relative; height: 300px; border-radius: 14px; overflow: hidden; border: 1px solid var(--glass-border);
		background: var(--glass-bg); margin: 12px 0 16px; }
	.art { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; object-position: 62% 25%; }
	.fade { position: absolute; inset: 0; background: linear-gradient(90deg, rgba(7, 10, 20, 0.95) 0%,
		rgba(7, 10, 20, 0.75) 30%, rgba(7, 10, 20, 0) 62%), linear-gradient(0deg, rgba(7, 10, 20, 0.85), transparent 30%); }
	.text { position: relative; padding: 24px 28px; }
	h1 { font-size: 36px; margin: 0; color: var(--el, var(--cream)); text-shadow: 0 2px 12px rgba(0, 0, 0, 0.6); }
	.meta { display: flex; gap: 8px; align-items: center; margin-top: 6px; color: var(--cream); }
	.stars { color: var(--rarity-5); letter-spacing: 2px; }
	.el { width: 22px; height: 22px; }
	.goal { display: flex; gap: 10px; align-items: center; margin-top: 14px; }
	.prio { font-size: 12px; padding: 3px 10px; border-radius: 999px; border: 1px solid var(--glass-border); color: var(--text); text-decoration: none; }
	.tabs { position: absolute; left: 0; right: 0; bottom: 0; display: flex; gap: 4px; padding: 0 20px; }
	.tabs a { padding: 10px 18px; color: var(--muted); text-decoration: none; border-bottom: 2px solid transparent; }
	.tabs a[aria-current='page'] { color: var(--el, var(--gold)); border-bottom-color: var(--el, var(--gold)); }
	@media (max-width: 900px) {
		.banner { height: 220px; }
		.fade { background: linear-gradient(90deg, rgba(7, 10, 20, 0.95) 0%, rgba(7, 10, 20, 0.6) 70%),
			linear-gradient(0deg, rgba(7, 10, 20, 0.85), transparent 30%); }
		h1 { font-size: 26px; }
	}
</style>
