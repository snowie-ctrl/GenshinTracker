<script lang="ts">
	import type { Targets } from './types';

	let { targets, levelCaps, onchange }: { targets: Targets; levelCaps: number[]; onchange: (t: Targets) => void } =
		$props();

	const TALENTS = [
		{ key: 'normal', label: 'Normal attack' },
		{ key: 'skill', label: 'Elemental skill' },
		{ key: 'burst', label: 'Elemental burst' }
	] as const;
	const TALENT_LEVELS = Array.from({ length: 10 }, (_, i) => i + 1);
	const WEAPON_LEVELS = [20, 40, 50, 60, 70, 80, 90];

	const levelOptions = $derived([...new Set([...levelCaps, targets.level])].sort((a, b) => a - b));
	const weaponOptions = $derived([...new Set([...WEAPON_LEVELS, targets.weapon_level])].sort((a, b) => a - b));

	function set(key: keyof Targets, value: number) {
		onchange({ ...targets, [key]: value });
	}
</script>

<div class="targets">
	<label>
		<span>Level</span>
		<select aria-label="Target level" value={targets.level}
			onchange={(e) => set('level', Number(e.currentTarget.value))}>
			{#each levelOptions as l (l)}<option value={l}>{l}</option>{/each}
		</select>
	</label>
	{#each TALENTS as t (t.key)}
		<label>
			<span>{t.label}</span>
			<select aria-label="Target {t.label.toLowerCase()}" value={targets[t.key]}
				onchange={(e) => set(t.key, Number(e.currentTarget.value))}>
				{#each TALENT_LEVELS as l (l)}<option value={l}>{l}</option>{/each}
			</select>
		</label>
	{/each}
	<label>
		<span>Weapon level</span>
		<select aria-label="Target weapon level" value={targets.weapon_level}
			onchange={(e) => set('weapon_level', Number(e.currentTarget.value))}>
			{#each weaponOptions as l (l)}<option value={l}>{l}</option>{/each}
		</select>
	</label>
</div>

<style>
	.targets { display: flex; flex-wrap: wrap; gap: 12px; }
	label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--muted); }
</style>
