<!-- frontend/src/lib/ProfileHeader.svelte -->
<script lang="ts">
	import { imgSrc } from './img';
	import { timeAgo } from './time';
	import type { ProfileHeaderView } from './types';

	let { header, portrait, fetchedAt, error, now }: {
		header: ProfileHeaderView; portrait: string | null; fetchedAt: string | null; error: string | null; now: number;
	} = $props();
</script>

<section class="panel hero" data-testid="profile-header">
	{#if imgSrc(portrait)}
		<img class="avatar" src={imgSrc(portrait)} alt="" />
	{:else}
		<span class="avatar initial" aria-hidden="true">{header.name.slice(0, 1)}</span>
	{/if}
	<div>
		<h1>{header.name} <span class="ar">AR {header.ar}</span></h1>
		<div class="muted">{header.days_active.toLocaleString()} days active · {header.achievements.toLocaleString()} achievements</div>
		<div class="muted small">as of {fetchedAt ? timeAgo(fetchedAt, now) : '—'}{#if error} · ⚠ last update failed: {error}{/if}</div>
	</div>
</section>

<style>
	.hero { display: flex; align-items: center; gap: 16px; margin-bottom: 12px;
		background: linear-gradient(90deg, color-mix(in srgb, var(--rarity-4) 35%, transparent), transparent); }
	.avatar { width: 72px; height: 72px; border-radius: 50%; border: 2px solid var(--rarity-5); object-fit: cover;
		background: var(--panel-2); }
	.initial { display: inline-flex; align-items: center; justify-content: center; font-size: 28px; font-weight: 700; }
	h1 { margin: 0; display: flex; align-items: center; gap: 8px; }
	.ar { background: var(--rarity-5); color: #17130b; border-radius: 999px; padding: 1px 10px; font-size: 13px; font-weight: 700; }
	.small { font-size: 12px; }
</style>
