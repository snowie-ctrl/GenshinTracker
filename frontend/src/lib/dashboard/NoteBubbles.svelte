<script lang="ts">
	import Icon from '$lib/Icon.svelte';
	import { expeditionsReady } from '$lib/dashboard';
	import { imgSrc } from '$lib/img';
	import { formatDuration } from '$lib/time';
	import type { Connection, Notes } from '$lib/types';

	let { notes, connection, now }: { notes: Notes | null; connection: Connection; now: number } = $props();
	const fullIn = (iso: string | null) => (iso ? Date.parse(iso) - now : null);
	const resinIn = $derived(notes ? fullIn(notes.resin_full_at) : null);
	const realmIn = $derived(notes ? fullIn(notes.realm_currency_full_at) : null);
	const ready = $derived(notes ? expeditionsReady(notes.expeditions, now) : 0);
	const expTotal = $derived(notes ? (notes.expeditions_max ?? notes.expeditions.length) : 0);
	const fullText = (ms: number | null) => (ms === null ? '' : ms <= 0 ? 'Full' : `Full in ${formatDuration(ms)}`);
</script>

{#if connection.status === 'missing'}
	<section class="panel" data-testid="bubbles">Connect HoYoLAB in <a href="/settings">Settings</a> to see your account here.</section>
{:else}
	<div class="bubbles" data-testid="bubbles">
		<section class="panel bubble" data-testid="bubble-resin">
			<img src={imgSrc('UI_ItemIcon_210')} alt="" />
			<div><div class="label">Original Resin</div>
				<div class="big">{notes ? notes.resin : '—'}{#if notes}<span class="muted">/{notes.resin_max}</span>{/if}</div>
				<div class="muted">{fullText(resinIn)}</div></div>
		</section>
		<section class="panel bubble" data-testid="bubble-commissions">
			<span class="icon"><Icon name="commission" size={36} /></span>
			<div><div class="label">Commissions</div>
				<div class="big">{notes ? notes.commissions_done : '—'}{#if notes}<span class="muted">/{notes.commissions_max}</span>{/if}</div>
				{#if notes && notes.commission_bonus_claimed !== null}
					<div class:ok={notes.commission_bonus_claimed} class="muted">{notes.commission_bonus_claimed ? 'Bonus claimed' : 'Bonus not claimed'}</div>
				{/if}</div>
		</section>
		<section class="panel bubble" data-testid="bubble-realm">
			<img src={imgSrc('UI_ItemIcon_204')} alt="" />
			<div><div class="label">Realm Currency</div>
				<div class="big">{notes ? notes.realm_currency : '—'}{#if notes}<span class="muted">/{notes.realm_currency_max}</span>{/if}</div>
				<div class="muted">{fullText(realmIn)}</div></div>
		</section>
		<section class="panel bubble" data-testid="bubble-expeditions">
			<span class="icon"><Icon name="expedition" size={36} /></span>
			<div><div class="label">Expeditions</div>
				<div class="big">{notes ? ready : '—'}{#if notes}<span class="muted">/{expTotal} ready</span>{/if}</div>
				{#if notes}<div class="exps">{#each notes.expeditions as e, i (i)}
					{#if imgSrc(e.icon)}<img class="exp" class:away={!(e.finished || Date.parse(e.return_at) <= now)} src={imgSrc(e.icon)} alt="" />{/if}
				{/each}</div>{/if}</div>
		</section>
	</div>
{/if}

<style>
	.bubbles { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; }
	.bubble { display: flex; gap: 12px; align-items: center; }
	.bubble > img, .icon { width: 44px; height: 44px; flex: none; display: inline-flex; align-items: center; justify-content: center; color: var(--gold); }
	.label { font-size: 13px; color: var(--muted); }
	.big { font-size: 26px; font-weight: 700; }
	.big .muted { font-size: 15px; font-weight: 400; }
	.ok { color: var(--accent); }
	.exps { display: flex; gap: 4px; margin-top: 4px; }
	.exp { width: 26px; height: 26px; border-radius: 50%; background: var(--panel-2); }
	.exp.away { opacity: 0.4; }
</style>
