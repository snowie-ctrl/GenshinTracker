<script lang="ts">
	import { imgSrc } from '$lib/img';
	import type { CharRef } from '$lib/types';
	let { completed }: { completed: CharRef[] } = $props();
</script>

{#if completed.length > 0}
	<section class="panel" data-testid="completed">
		<h2>Completed builds</h2>
		<div class="row">
			{#each completed as c (c.id)}
				<a href="/characters/{c.slug}" title={c.name}>
					{#if imgSrc(c.icon)}<img src={imgSrc(c.icon)} alt="" />{:else}<span class="initial">{c.name.slice(0, 1)}</span>{/if}
					<span>{c.name}</span>
				</a>
			{/each}
		</div>
	</section>
{/if}

<style>
	.row { display: flex; flex-wrap: wrap; gap: 12px; }
	a { display: inline-flex; flex-direction: column; align-items: center; gap: 4px; font-size: 12px; color: inherit; text-decoration: none; width: 64px; text-align: center; }
	img, .initial { width: 48px; height: 48px; border-radius: 50%; background: var(--r0); display: inline-flex; align-items: center; justify-content: center; }
</style>
