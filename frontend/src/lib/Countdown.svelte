<script lang="ts">
	import { timeLeft } from './events';
	let { at, now }: { at: string | null; now: number } = $props();
	const soon = $derived(!!at && Date.parse(at) - now < 24 * 3600 * 1000);
</script>

<span class="cd" class:soon title={at ?? ''}>{timeLeft(at, now)}</span>

<style>
	.cd { font-variant-numeric: tabular-nums; }
	.soon { color: var(--warn); }
</style>
