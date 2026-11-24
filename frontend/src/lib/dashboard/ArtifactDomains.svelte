<!-- frontend/src/lib/dashboard/ArtifactDomains.svelte -->
<script lang="ts">
	import { elementStyle } from '$lib/elements';
	import { imgSrc } from '$lib/img';
	import type { ArtifactDomainsView, ArtifactSetRow } from '$lib/types';

	let { view }: { view: ArtifactDomainsView } = $props();
	const shown = $derived(view.domains.length > 0 || view.other.length > 0 || view.hint !== null);
</script>

{#snippet setRow(s: ArtifactSetRow)}
	{#if s.needed}
		<div class="set-row" data-testid="artifact-set-row-{s.id}">
			<div class="set-name">{s.name}</div>
			<div class="avatars">
				{#each s.characters as c (c.id)}
					<a href="/characters/{c.slug}/build" title="{c.name} · {c.pieces}pc · {c.equipped}/{c.pieces} equipped">
						{#if imgSrc(c.icon)}<img src={imgSrc(c.icon)} alt={c.name} />{/if}
						<span class="hint">{c.pieces}pc · {c.equipped}/{c.pieces}</span>
					</a>
				{/each}
			</div>
		</div>
	{/if}
{/snippet}

{#if shown}
	<section class="panel" data-testid="artifact-domains">
		<h2>Artifact domains</h2>
		{#if view.hint}
			<p class="muted" data-testid="artifact-hint">{view.hint}</p>
		{/if}
		<div class="cards">
			{#each view.domains as d (d.id)}
				<div class="card" data-testid="artifact-domain-{d.id}">
					<div class="art">
						{#each d.sets as s (s.id)}
							<div class="set-icon" class:dim={!s.needed} title={s.name}>
								{#if imgSrc(s.icon)}<img src={imgSrc(s.icon)} alt={s.name} />{/if}
							</div>
						{/each}
					</div>
					<div class="title">{d.entrance}</div>
					<div class="muted small">{d.region ?? ''}{#each d.elements as el (el)}{#if imgSrc(elementStyle(el).icon)}<img class="el" src={imgSrc(elementStyle(el).icon)} alt={el} title={el} />{/if}{/each}</div>
					{#each d.sets as s (s.id)}{@render setRow(s)}{/each}
				</div>
			{/each}
			{#if view.other.length}
				<div class="card" data-testid="artifact-other">
					<div class="title">{view.sources_known ? 'Not from a domain' : 'Drop source unknown'}</div>
					{#if view.sources_known}<div class="muted small">Bosses / Strongbox</div>{/if}
					{#each view.other as s (s.id)}{@render setRow(s)}{/each}
				</div>
			{/if}
		</div>
	</section>
{/if}

<style>
	.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; margin-top: 10px; }
	.card { background: var(--panel-2); border: 1px solid var(--line); border-radius: 10px; padding: 10px; }
	.art { display: flex; gap: 8px; justify-content: center; padding: 6px; border-radius: 8px;
		background: linear-gradient(135deg, var(--panel), var(--panel-2)); margin-bottom: 6px; }
	.set-icon img { width: 72px; height: 72px; display: block; }
	.set-icon.dim { opacity: 0.3; filter: grayscale(1); }
	.title { font-weight: 600; }
	.small { font-size: 11px; }
	.el { width: 16px; height: 16px; vertical-align: middle; margin-left: 4px; }
	.set-row { margin-top: 8px; }
	.set-name { font-size: 12px; }
	.avatars { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
	.avatars a { display: flex; flex-direction: column; align-items: center; text-decoration: none; color: var(--muted); }
	.avatars img { width: 28px; height: 28px; border-radius: 50%; background: var(--r0); }
	.hint { font-size: 10px; }
</style>
