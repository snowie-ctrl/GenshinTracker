<script lang="ts">
	import { api, errorMessage } from './api';
	import { importSummaryText } from './good';
	import type { GoodSummary } from './types';

	let { onimported }: { onimported?: (s: GoodSummary) => void } = $props();
	let input: HTMLInputElement;
	let busy = $state(false);
	let message = $state<string | null>(null);
	let failed = $state(false);

	async function pick(e: Event & { currentTarget: HTMLInputElement }) {
		const file = e.currentTarget.files?.[0];
		e.currentTarget.value = '';
		if (!file) return;
		busy = true;
		try {
			const s = await api.importGood(file);
			message = importSummaryText(s);
			failed = false;
			onimported?.(s);
		} catch (err) {
			message = errorMessage(err);
			failed = true;
		} finally {
			busy = false;
		}
	}
</script>

<input bind:this={input} type="file" accept=".json,application/json" hidden data-testid="good-file-input" onchange={pick} />
<button type="button" onclick={() => input.click()} disabled={busy}>{busy ? 'Importing…' : 'Import GOOD file'}</button>
{#if message}<span class:error={failed} class:muted={!failed} data-testid="good-toast" role="status">{message}</span>{/if}
