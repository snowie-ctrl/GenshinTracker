<script lang="ts">
	import { valueAt, type Column } from './kit';
	import type { ScaleRow } from './types';

	let { rows, columns }: { rows: ScaleRow[]; columns: Column[] } = $props();
</script>

{#if rows.length}
	<table>
		<thead><tr><th></th>{#each columns as c (c.key)}<th class={c.key}>{c.label}</th>{/each}</tr></thead>
		<tbody>
			{#each rows as r, i (i)}
				<tr><td class="label">{r.label}</td>{#each columns as c (c.key)}<td class={c.key}>{valueAt(r, c.level)}</td>{/each}</tr>
			{/each}
		</tbody>
	</table>
{/if}

<style>
	table { font-size: 12px; border-collapse: collapse; margin-top: 4px; }
	th { color: var(--muted); font-weight: 500; text-align: right; padding: 2px 10px; }
	td { padding: 2px 10px; text-align: right; }
	td.label { text-align: left; padding-left: 0; color: var(--muted); }
	td.target { color: var(--el, var(--gold)); font-weight: 600; }
</style>
