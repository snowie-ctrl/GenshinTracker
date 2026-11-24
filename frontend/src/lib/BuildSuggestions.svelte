<script lang="ts">
	import { MAIN_SLOTS, STAT_LABELS } from './artifacts';
	import { getCharacterPage } from './characterPage.svelte';
	import { applyRecommendation, matchesRecommendation } from './recommend';

	let { editing }: { editing: boolean } = $props();
	const p = getCharacterPage();
	const c = $derived(p.c!);
	const rec = $derived(c.stat_recommendation);
	const matches = $derived(rec ? matchesRecommendation(c.artifact_target, rec) : false);
	let saving = $state(false);

	async function apply() {
		if (!rec || saving) return;
		saving = true;
		try {
			await p.saveGoal({ artifact_target: applyRecommendation(c.artifact_target, rec) });
		} finally {
			saving = false;
		}
	}
	const label = (k: string) => STAT_LABELS[k] ?? k;
	const date = (iso: string) => iso.slice(0, 10);
</script>

<section class="card" data-testid="build-suggestions">
	<h2>Suggestions</h2>
	{#if rec}
		<p class="muted small">HoYoLAB recommends · synced {date(rec.synced_at)}</p>
		{#each MAIN_SLOTS as slot (slot)}
			<div class="row">
				<span class="label">{slot[0].toUpperCase() + slot.slice(1)}</span>
				{#each rec.main[slot] as key (key)}
					<span class="pill" data-testid="suggestion-{slot}-{key}">{label(key)}</span>
				{:else}
					<span class="muted small">No preference</span>
				{/each}
			</div>
		{/each}
		<div class="row">
			<span class="label">Substats</span>
			{#each rec.subs as key, i (key)}
				<span class="pill" data-testid="suggestion-sub-{key}">{i + 1}. {label(key)}</span>
			{/each}
		</div>
		{#if matches}
			<p class="ok small" data-testid="suggestions-match">Your target matches.</p>
		{:else if editing}
			<button type="button" data-testid="suggestions-apply" disabled={saving} onclick={apply}>
				Apply to artifact target
			</button>
		{/if}
	{:else}
		<p class="muted" data-testid="suggestions-empty">
			No HoYoLAB recommendation yet. It arrives with the next sync of an owned character.
		</p>
	{/if}
	<p class="muted small foot">Talent, set and team suggestions are not available from any open source.</p>
</section>

<style>
	.row { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; margin-bottom: 6px; }
	.label { width: 64px; font-size: 12px; color: var(--muted); }
	.pill { font-size: 12px; padding: 2px 8px; border-radius: 999px; border: 1px solid var(--el, var(--gold));
		color: var(--text); }
	.small { font-size: 11px; }
	.ok { color: var(--building); }
	.foot { margin-top: 10px; }
	button { margin-top: 6px; }
</style>
