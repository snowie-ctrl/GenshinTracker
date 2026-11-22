<script lang="ts">
	import { onMount } from 'svelte';
	import Icon from './Icon.svelte';
	import { sync } from './sync.svelte';
	import { lastFinished, skippedNote, syncBadge, syncLabel } from './syncLabel';

	let now = $state(Date.now());
	let open = $state(false);
	const badge = $derived(syncBadge(sync.status, now));
	const last = $derived(lastFinished(sync.status));

	onMount(() => {
		const t = setInterval(() => (now = Date.now()), 30_000);
		return () => clearInterval(t);
	});
</script>

<div class="sync">
	<button type="button" class="item" data-testid="sync-label" aria-expanded={open}
		title={syncLabel(sync.status, now)} onclick={() => (open = !open)}>
		<span class="icon" class:spin={badge.running}><Icon name="sync" /></span>
		{#if badge.tone !== 'none'}<span class="dot {badge.tone}" aria-hidden="true"></span>{/if}
		<span class="label">{badge.short}</span>
	</button>
	{#if open}
		<div class="popover" data-testid="sync-popover">
			<div class="row">
				<b>{syncLabel(sync.status, now)}</b>
				<button type="button" class="primary" onclick={() => sync.start('manual')}
					disabled={sync.status?.running || sync.connection?.status !== 'connected'}>Sync now</button>
			</div>
			{#if last}
				<div class="muted">Last sync ({last.trigger})</div>
				{#each Object.entries(last.parts) as [name, part] (name)}
					<div>
						<b>{name}</b>:
						{#if part.ok}ok{#if skippedNote(part)} ({skippedNote(part)}){/if}{#if part.count !== undefined} ({part.count}){/if}{:else}<span class="error">{part.error}</span>{/if}
					</div>
				{/each}
			{/if}
			{#if sync.error}<div class="error">{sync.error}</div>{/if}
		</div>
	{/if}
</div>

<style>
	.sync { position: relative; width: 100%; }
	.item {
		position: relative; width: 100%; display: flex; flex-direction: column; align-items: center; gap: 3px;
		padding: 7px 0; background: none; border: none; border-radius: 0; color: var(--cream-dim); font-size: 10.5px;
	}
	.item:hover { color: var(--cream); background: none; }
	.label { max-width: 70px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
	.dot { position: absolute; top: 6px; right: 22px; width: 7px; height: 7px; border-radius: 50%; }
	.dot.ok { background: var(--building); }
	.dot.warn { background: var(--warn); }
	.spin { display: inline-flex; animation: spin 1.2s linear infinite; }
	@media (prefers-reduced-motion: reduce) { .spin { animation: none; } }
	@keyframes spin { to { transform: rotate(360deg); } }
	.popover {
		position: absolute; left: calc(100% + 10px); bottom: 0; z-index: 50; min-width: 280px; padding: 12px;
		font-size: 12px; background: var(--glass-bg-strong); border: 1px solid var(--glass-border); border-radius: 12px;
		box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5); backdrop-filter: blur(var(--glass-blur));
	}
	.row { display: flex; justify-content: space-between; align-items: center; gap: 10px; margin-bottom: 8px; }
</style>
