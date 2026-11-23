<script lang="ts">
	import { greeting } from '$lib/dashboard';
	let { name, now }: { name: string; now: number } = $props();
	const text = $derived(greeting(new Date(now).getHours(), name));
</script>

<h1 class="greeting" data-testid="greeting">{text}</h1>

<style>
	.greeting { margin: 0 0 12px; font-size: 26px; }
</style>
