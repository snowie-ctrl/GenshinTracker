<script lang="ts">
	import { page } from '$app/state';
	import TeamEditor from '$lib/TeamEditor.svelte';

	const id = $derived(Number(page.params.id));
</script>

{#key id}
	{#if Number.isInteger(id)}
		<TeamEditor teamId={id} />
	{:else}
		<p>This team no longer exists. <a href="/teams">Back to Teams</a></p>
	{/if}
{/key}
