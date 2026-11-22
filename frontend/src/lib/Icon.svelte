<script lang="ts">
	import { ICONS, type IconName } from './icons';

	let { name, size = 22 }: { name: IconName; size?: number } = $props();
</script>

<svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false">
	{#each ICONS[name] as p, i (i)}
		<path d={p.d} fill-rule={p.evenodd ? 'evenodd' : undefined} />
	{/each}
</svg>
