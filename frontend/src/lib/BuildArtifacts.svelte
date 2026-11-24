<script lang="ts">
	import { api } from './api';
	import ArtifactSetPicker from './ArtifactSetPicker.svelte';
	import { emptyTarget, MAIN_SLOTS, setSlot, setsFor, SLOT_OPTIONS, STAT_LABELS, toggleStat } from './artifacts';
	import { getCharacterPage } from './characterPage.svelte';
	import { imgSrc } from './img';
	import StatPills from './StatPills.svelte';
	import SubstatOrder from './SubstatOrder.svelte';
	import type { ArtifactSetOption, ArtifactTarget, MainSlot } from './types';

	let { editing }: { editing: boolean } = $props();
	const p = getCharacterPage();
	const c = $derived(p.c!);
	const loaded = $derived<ArtifactTarget>(c.artifact_target ?? emptyTarget());
	const check = $derived(c.artifact_check);

	let options = $state<ArtifactSetOption[]>([]);
	$effect(() => { api.artifactSets().then((o) => (options = o)).catch(() => (options = [])); });

	// Rapid edits build on the latest unsaved draft (same pattern as the Build page targets).
	let draft: ArtifactTarget | null = null;
	let inflight = $state(0);
	const t = $derived(loaded);
	let resetKey = $state(0);
	let modeOverride = $state<4 | 2 | null>(null);
	const mode = $derived<4 | 2>(modeOverride ?? (t.sets.length === 2 || t.sets[0]?.pieces === 2 ? 2 : 4));

	async function save(next: ArtifactTarget) {
		draft = next;
		inflight++;
		try {
			await p.saveGoal({ artifact_target: next });
		} finally {
			if (--inflight === 0) { draft = null; if (t.sets.length) modeOverride = null; }
		}
	}
	const base = () => draft ?? t;
	function setMode(m: 4 | 2) {
		modeOverride = m;
		const cur = base();
		if (cur.sets.length) save({ ...cur, sets: setsFor(m, cur.sets) });
	}
	function pick(index: number, id: number | null) {
		const cur = base();
		const sets = setSlot(cur.sets, index, id, mode);
		if (sets === cur.sets) { resetKey++; return; } // duplicate ignored: show the stored value again
		save({ ...cur, sets });
	}
	function toggleMain(slot: MainSlot, key: string) {
		const cur = base();
		save({ ...cur, main: { ...cur.main, [slot]: toggleStat(cur.main[slot], key) } });
	}
	function setSubs(subs: string[]) { save({ ...base(), subs }); }
	async function setDone(done: boolean) {
		inflight++;
		try { await p.saveGoal({ artifacts_done: done }); } finally { inflight--; }
	}
	const SLOT_LABEL: Record<string, string> = { flower: 'Flower', plume: 'Plume', sands: 'Sands', goblet: 'Goblet', circlet: 'Circlet' };
</script>

<section class="card span2" data-testid="build-artifacts">
	<h2>Artifacts</h2>
	<fieldset disabled={!editing || inflight > 0}>
		<div class="sets">
			<div class="mode" role="group" aria-label="Set mode">
				<button type="button" class:on={mode === 4} aria-pressed={mode === 4} data-testid="artifact-mode-4" onclick={() => setMode(4)}>4-piece</button>
				<button type="button" class:on={mode === 2} aria-pressed={mode === 2} data-testid="artifact-mode-2" onclick={() => setMode(2)}>2 + 2</button>
			</div>
			{#key resetKey}
				<ArtifactSetPicker index={0} {options} value={t.sets[0]?.set_id ?? null} onchange={(id) => pick(0, id)} />
				{#if mode === 2}
					<ArtifactSetPicker index={1} {options} value={t.sets[1]?.set_id ?? null} onchange={(id) => pick(1, id)} />
				{/if}
			{/key}
		</div>

		<h3>Main stats</h3>
		<div class="mains">
			<div class="fixed muted small">Flower HP · Plume ATK</div>
			{#each MAIN_SLOTS as slot (slot)}
				<StatPills {slot} options={SLOT_OPTIONS[slot]} selected={t.main[slot]} onchange={(k) => toggleMain(slot, k)} />
			{/each}
		</div>

		<h3>Substat priority</h3>
		<SubstatOrder subs={t.subs} onchange={setSubs} />
	</fieldset>

	<h3>Equipped</h3>
	<div class="equipped">
		{#each check.slots as s (s.slot)}
			<div class="piece" data-testid="equipped-{s.slot}">
				{#if imgSrc(s.icon)}<img src={imgSrc(s.icon)} alt={s.set_name} />{/if}
				<span class="muted small">{SLOT_LABEL[s.slot] ?? s.slot}</span>
				<span class="small">{s.key ? (STAT_LABELS[s.key] ?? s.main_stat) : s.main_stat}</span>
				{#if s.ok === true}<span class="ok">✓</span>{:else if s.ok === false}<span class="bad">✗</span>{/if}
			</div>
		{/each}
	</div>
	<div class="status">
		<span data-testid="artifact-status">
			{#if check.status === 'met'}Matches target
			{:else if check.status === 'missing'}{#if check.missing.length === 1 && check.missing[0] === 'No artifacts equipped'}No artifacts equipped{:else}Missing: {check.missing.join(', ')}{/if}
			{:else}No artifact target set{/if}
		</span>
		{#each check.sets as s (s.set_id)}<span class="muted small">{s.name} {s.equipped}/{s.pieces}</span>{/each}
		<label class="done">
			<input type="checkbox" data-testid="artifacts-done" checked={c.artifacts_done} disabled={!editing || inflight > 0}
				onchange={(e) => setDone(e.currentTarget.checked)} />
			Artifacts done
		</label>
	</div>
</section>

<style>
	fieldset { border: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 10px; }
	.sets { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
	.mode { display: flex; gap: 4px; }
	.mode button { border: 1px solid var(--glass-border); background: transparent; color: var(--text); border-radius: 999px; padding: 3px 10px; }
	.mode button.on { background: var(--el, var(--gold)); color: var(--bg); }
	h3 { margin: 6px 0 2px; font-size: 13px; color: var(--muted); }
	.mains { display: flex; flex-direction: column; gap: 6px; }
	.equipped { display: flex; flex-wrap: wrap; gap: 10px; }
	.piece { display: flex; flex-direction: column; align-items: center; gap: 2px; min-width: 64px; }
	.piece img { width: 40px; height: 40px; }
	.ok { color: var(--building); }
	.bad { color: var(--danger, #e06c6c); }
	.status { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-top: 8px; }
	.done { margin-left: auto; display: flex; gap: 6px; align-items: center; }
	.small { font-size: 11px; }
</style>
