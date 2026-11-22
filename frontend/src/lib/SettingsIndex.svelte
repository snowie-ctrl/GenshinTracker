<script lang="ts">
	import { onMount } from 'svelte';

	let { sections }: { sections: { id: string; label: string }[] } = $props();
	let current = $state('');

	onMount(() => {
		current = sections[0]?.id ?? '';
		const observer = new IntersectionObserver(
			(entries) => {
				const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
				if (visible[0]) current = visible[0].target.id;
			},
			{ rootMargin: '0px 0px -60% 0px' }
		);
		for (const s of sections) {
			const el = document.getElementById(s.id);
			if (el) observer.observe(el);
		}
		return () => observer.disconnect();
	});
</script>

<nav class="index glass" aria-label="Settings sections">
	{#each sections as s (s.id)}
		<a href="#{s.id}" class:current={current === s.id} aria-current={current === s.id ? 'true' : undefined}>{s.label}</a>
	{/each}
</nav>

<style>
	.index { position: sticky; top: var(--gutter); display: flex; flex-direction: column; padding: 8px; gap: 2px; }
	a { padding: 6px 12px; border-radius: 8px; color: var(--cream-dim); text-decoration: none; font-size: 13px; }
	a:hover { color: var(--cream); }
	a.current { color: var(--gold); background: rgba(232, 207, 156, 0.1); }
	@media (max-width: 900px) {
		.index { position: static; flex-direction: row; flex-wrap: wrap; }
	}
</style>
