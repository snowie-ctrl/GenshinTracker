<script lang="ts">
	import { api, errorMessage } from '$lib/api';
	import { clampCons, clampTalent, editable, unlockLocked } from '$lib/traveler';
	import type { TravelerInfo } from '$lib/types';

	let { info, onsaved }: { info: TravelerInfo; onsaved: () => void } = $props();
	let error = $state<string | null>(null);

	async function save(body: Parameters<typeof api.setTraveler>[1]) {
		try {
			await api.setTraveler(info.element_id, body);
			error = null;
			onsaved();
		} catch (e) {
			error = errorMessage(e);
		}
	}

	function talent(key: 'normal' | 'skill' | 'burst', value: string) {
		save({ talents: { ...info.talents, [key]: clampTalent(Number(value)) } });
	}
</script>

<section class="panel" data-testid="traveler-element">
	<h2>Traveler element</h2>
	<label class="row">
		<input type="checkbox" checked={info.seen || info.unlocked} disabled={unlockLocked(info)}
			onchange={(e) => save({ unlocked: e.currentTarget.checked })} />
		<span>Unlocked</span>
	</label>
	{#if info.current}<p class="muted">From HoYoLAB: current element</p>{/if}
	<div class="fields">
		{#each [['normal', 'Normal attack'], ['skill', 'Skill'], ['burst', 'Burst']] as [key, label] (key)}
			<label>
				<span>{label}</span>
				<input type="number" min="1" max="10" value={info.talents[key as 'normal' | 'skill' | 'burst']}
					disabled={!editable(info)} aria-label={label}
					onchange={(e) => talent(key as 'normal' | 'skill' | 'burst', e.currentTarget.value)} />
			</label>
		{/each}
		<label>
			<span>Constellation</span>
			<input type="number" min="0" max="6" value={info.constellation} disabled={!editable(info)}
				aria-label="Constellation"
				onchange={(e) => save({ constellation: clampCons(Number(e.currentTarget.value)) })} />
		</label>
	</div>
	{#if error}<p class="error">{error}</p>{/if}
</section>

<style>
	.row { display: inline-flex; gap: 8px; align-items: center; }
	.fields { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 10px; }
	.fields label { display: inline-flex; flex-direction: column; gap: 4px; }
	.fields input { width: 5rem; }
</style>
