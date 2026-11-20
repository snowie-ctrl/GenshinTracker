<script lang="ts">
	import type { Goal } from './types';

	let { goal, onchange, compact = false }: { goal: Goal; onchange: (g: Goal) => void; compact?: boolean } =
		$props();

	const OPTIONS: { value: Goal; label: string }[] = [
		{ value: 'none', label: 'None' },
		{ value: 'want', label: 'Want' },
		{ value: 'build', label: 'Build' }
	];
</script>

<div class="goal-switch" class:compact role="group" aria-label="Goal">
	{#each OPTIONS as o (o.value)}
		<button
			type="button"
			class:active={goal === o.value}
			aria-pressed={goal === o.value}
			onclick={() => {
				if (goal !== o.value) onchange(o.value);
			}}>{o.label}</button
		>
	{/each}
</div>

<style>
	.goal-switch { display: inline-flex; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }
	.goal-switch button { border: none; border-radius: 0; background: var(--panel-2); padding: 4px 12px; }
	.goal-switch button.active { background: var(--accent); color: #111; font-weight: 600; }
	/* Compact mode sits on a 104px character card: share the width evenly so all three fit. */
	.compact { width: 96px; }
	.compact button { flex: 1; padding: 2px 0; font-size: 10px; }
</style>
