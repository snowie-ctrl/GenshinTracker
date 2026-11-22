<script lang="ts">
	import { countdownWarn, timeLeft } from './events';
	// warn: set for event and banner end times; resets, done events and past times stay neutral.
	let { at, now, warn = false }: { at: string | null; now: number; warn?: boolean } = $props();
	const soon = $derived(countdownWarn(at, now, warn));
</script>

<span class="cd" class:soon title={at ?? ''}>{timeLeft(at, now)}</span>

<style>
	.cd { font-variant-numeric: tabular-nums; }
	.soon { color: var(--warn); }
</style>
