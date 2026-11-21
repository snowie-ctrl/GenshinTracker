<script lang="ts">
	import { onMount } from 'svelte';
	import { api, errorMessage } from './api';
	import TagChip from './TagChip.svelte';
	import { TAG_COLORS, TAG_HEX } from './teams';
	import type { TagWithCount } from './types';

	let { onChange }: { onChange: () => void } = $props();
	let tags = $state<TagWithCount[]>([]);
	let newName = $state('');
	let error = $state<string | null>(null);

	onMount(load);

	async function load() {
		try {
			tags = await api.tags();
		} catch (e) {
			error = errorMessage(e);
		}
	}

	async function run(fn: () => Promise<unknown>) {
		try {
			await fn();
			error = null;
			await load();
			onChange();
		} catch (e) {
			error = errorMessage(e);
		}
	}

	function rename(t: TagWithCount, name: string) {
		if (name.trim() && name.trim() !== t.name) run(() => api.updateTag(t.id, { name: name.trim() }));
	}

	function remove(t: TagWithCount) {
		const n = t.team_count;
		if (confirm(`Delete tag "${t.name}"? ${n} ${n === 1 ? 'team loses' : 'teams lose'} it. Goals are not changed.`)) {
			run(() => api.deleteTag(t.id));
		}
	}

	function create(ev: SubmitEvent) {
		ev.preventDefault();
		const name = newName.trim();
		if (name) run(async () => { await api.createTag(name); newName = ''; });
	}
</script>

<section class="panel" data-testid="tag-manager">
	<h2>Tags</h2>
	{#if error}<p class="error">{error}</p>{/if}
	<ul>
		{#each tags as t (t.id)}
			<li>
				<TagChip tag={t} />
				{#if t.builtin}
					<span class="muted">built-in</span>
				{:else}
					<input value={t.name} aria-label="Rename {t.name}" maxlength="30"
						onchange={(e) => rename(t, (e.currentTarget as HTMLInputElement).value)} />
				{/if}
				<span class="swatches">
					{#each TAG_COLORS as c (c)}
						<button type="button" class="sw" class:on={t.color === c} style="background: {TAG_HEX[c]}"
							aria-label="Colour {c} for {t.name}" onclick={() => run(() => api.updateTag(t.id, { color: c }))}></button>
					{/each}
				</span>
				<span class="muted">{t.team_count} {t.team_count === 1 ? 'team' : 'teams'}</span>
				{#if !t.builtin}<button type="button" onclick={() => remove(t)}>Delete</button>{/if}
			</li>
		{/each}
	</ul>
	<form onsubmit={create}>
		<input bind:value={newName} placeholder="New tag" maxlength="30" aria-label="New tag name" />
		<button type="submit">Add tag</button>
	</form>
</section>

<style>
	ul { list-style: none; padding: 0; margin: 0 0 8px; }
	li { display: flex; align-items: center; gap: 8px; padding: 4px 0; flex-wrap: wrap; }
	.swatches { display: inline-flex; gap: 3px; }
	.sw { width: 16px; height: 16px; border-radius: 50%; border: 2px solid transparent; padding: 0; cursor: pointer; }
	.sw.on { border-color: var(--text); }
</style>
