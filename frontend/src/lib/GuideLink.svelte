<script lang="ts">
	import { communityGuideUrl } from './guides';

	let { slug }: { slug: string } = $props();
</script>

<section class="card howto" data-testid="guide-howto">
	<h2>How to play</h2>
	<a data-testid="community-guide-link" href={communityGuideUrl(slug)} target="_blank" rel="noopener noreferrer">
		Community build guide ↗
	</a>
	<p class="muted small">
		Third-party guide by the Genshin Impact Helper Team (all rights reserved), not affiliated with Ad Astra.
	</p>
</section>

<style>
	.howto { margin-bottom: 12px; }
	a { color: var(--el, var(--gold)); font-weight: 600; }
	.small { font-size: 11px; margin-top: 6px; }
</style>
