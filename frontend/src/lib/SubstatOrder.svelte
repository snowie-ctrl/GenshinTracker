<script lang="ts">
	import { moveSub, STAT_LABELS, SUB_KEYS } from './artifacts';

	let { subs, onchange }: { subs: string[]; onchange: (next: string[]) => void } = $props();
	const left = $derived(SUB_KEYS.filter((k) => !subs.includes(k)));
</script>

<ol class="subs">
	{#each subs as key, i (key)}
		<li class="chip" data-testid="sub-{key}">
			<span class="n">{i + 1}</span>{STAT_LABELS[key] ?? key}
			<button type="button" aria-label="Move {STAT_LABELS[key]} up" data-testid="sub-up-{key}" disabled={i === 0}
				onclick={() => onchange(moveSub(subs, i, i - 1))}>↑</button>
			<button type="button" aria-label="Move {STAT_LABELS[key]} down" data-testid="sub-down-{key}" disabled={i === subs.length - 1}
				onclick={() => onchange(moveSub(subs, i, i + 1))}>↓</button>
			<button type="button" aria-label="Remove {STAT_LABELS[key]}" data-testid="sub-remove-{key}"
				onclick={() => onchange(subs.filter((k) => k !== key))}>✕</button>
		</li>
	{/each}
	{#if left.length}
		<li>
			<select aria-label="Add substat" data-testid="sub-add" value=""
				onchange={(e) => { const v = e.currentTarget.value; if (v) onchange([...subs, v]); e.currentTarget.value = ''; }}>
				<option value="">Add substat…</option>
				{#each left as key (key)}<option value={key}>{STAT_LABELS[key]}</option>{/each}
			</select>
		</li>
	{/if}
</ol>

<style>
	.subs { display: flex; flex-wrap: wrap; gap: 6px; list-style: none; padding: 0; margin: 0; }
	.chip { display: inline-flex; align-items: center; gap: 4px; border: 1px solid var(--glass-border); border-radius: 999px; padding: 2px 8px; font-size: 12px; }
	.n { color: var(--el, var(--gold)); font-weight: 700; }
	.chip button { background: none; border: none; color: var(--muted); cursor: pointer; padding: 0 2px; }
</style>
