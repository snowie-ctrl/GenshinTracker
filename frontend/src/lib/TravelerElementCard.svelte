<script lang="ts">
	import { api, errorMessage } from '$lib/api';
	import { clampCons, clampTalent, editable, unlockLocked } from '$lib/traveler';
	import type { TravelerInfo } from '$lib/types';

	let { info, onsaved }: { info: TravelerInfo; onsaved: () => void | Promise<void> } = $props();
	let error = $state<string | null>(null);
	let saving = $state(false);

	// Save, then put the control back on what `info` says (the DOM owns the value after an edit).
	async function save(body: Parameters<typeof api.setTraveler>[1], reset: () => void) {
		saving = true;
		try {
			await api.setTraveler(info.element_id, body);
			error = null;
			await onsaved();
		} catch (e) {
			error = errorMessage(e);
		} finally {
			saving = false;
			reset();
		}
	}

	type Key = 'normal' | 'skill' | 'burst';
	function talent(key: Key, el: HTMLInputElement) {
		save({ talents: { ...info.talents, [key]: clampTalent(Number(el.value)) } },
			() => { el.value = String(info.talents[key]); });
	}
</script>

<section class="panel" data-testid="traveler-element">
	<h2>Traveler element</h2>
	<label class="row">
		<input type="checkbox" checked={info.seen || info.unlocked} disabled={unlockLocked(info) || saving}
			onchange={(e) => { const el = e.currentTarget; save({ unlocked: el.checked }, () => { el.checked = info.seen || info.unlocked; }); }} />
		<span>Unlocked</span>
	</label>
	{#if info.current}<p class="muted">From HoYoLAB: current element</p>{/if}
	<div class="fields">
		{#each [['normal', 'Normal attack'], ['skill', 'Skill'], ['burst', 'Burst']] as [key, label] (key)}
			<label>
				<span>{label}</span>
				<input type="number" min="1" max="10" value={info.talents[key as 'normal' | 'skill' | 'burst']}
					disabled={!editable(info) || saving} aria-label={label}
					onchange={(e) => talent(key as Key, e.currentTarget)} />
			</label>
		{/each}
		<label>
			<span>Constellation</span>
			<input type="number" min="0" max="6" value={info.constellation} disabled={!editable(info) || saving}
				aria-label="Constellation"
				onchange={(e) => { const el = e.currentTarget; save({ constellation: clampCons(Number(el.value)) }, () => { el.value = String(info.constellation); }); }} />
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
