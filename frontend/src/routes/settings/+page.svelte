<script lang="ts">
	import { api, errorMessage } from '$lib/api';
	import { sync } from '$lib/sync.svelte';
	import TargetsEditor from '$lib/TargetsEditor.svelte';
	import { timeAgo } from '$lib/time';
	import type { Account, Settings, SyncRun, Targets } from '$lib/types';

	const FIELDS = [
		{ key: 'ltuid_v2', required: true },
		{ key: 'ltoken_v2', required: true },
		{ key: 'ltmid_v2', required: false },
		{ key: 'account_id_v2', required: false },
		{ key: 'account_mid_v2', required: false },
		{ key: 'cookie_token_v2', required: false }
	] as const;

	let settings = $state<Settings | null>(null);
	let runs = $state<SyncRun[]>([]);
	let error = $state<string | null>(null);
	let showForm = $state(false);
	let cookie = $state<Record<string, string>>({});
	let accounts = $state<Account[] | null>(null);
	let connecting = $state(false);
	let connectError = $state<string | null>(null);
	let interval = $state(10);
	let savedNote = $state<string | null>(null);
	let refreshing = $state(false);
	const now = Date.now();

	$effect(() => {
		void sync.version;
		load();
	});

	async function load() {
		try {
			const [s, st] = await Promise.all([api.settings(), api.syncStatus()]);
			settings = s;
			runs = st.runs;
			interval = s.sync_interval_minutes;
			showForm = showForm || s.connection.status !== 'connected';
			error = null;
		} catch (e) {
			error = errorMessage(e);
		}
	}

	async function submit(uid?: number) {
		connecting = true;
		connectError = null;
		try {
			const body: Record<string, string | number> = { ...cookie };
			if (uid !== undefined) body.uid = uid;
			const r = await api.connect(body);
			if (r.status === 'choose') {
				accounts = r.accounts;
			} else {
				accounts = null;
				cookie = {};
				showForm = false;
				await sync.loadConnection();
				await sync.poll();
				await load();
			}
		} catch (e) {
			connectError = errorMessage(e);
		} finally {
			connecting = false;
		}
	}

	async function saveInterval() {
		try {
			settings = await api.saveSettings({ sync_interval_minutes: interval });
			savedNote = 'Saved.';
		} catch (e) {
			savedNote = errorMessage(e);
		}
	}

	async function saveTargets(t: Targets) {
		try {
			settings = await api.saveSettings({ default_targets: t });
		} catch (e) {
			error = errorMessage(e);
		}
	}

	async function refreshGamedata() {
		refreshing = true;
		try {
			await api.refreshGamedata();
			await load();
		} finally {
			refreshing = false;
		}
	}
</script>

<h1>Settings</h1>
{#if error}<p class="error">{error}</p>{/if}

{#if settings}
	<section class="panel">
		<h2>HoYoLAB</h2>
		{#if settings.connection.status === 'connected'}
			<p>Connected as UID {settings.connection.uid}.</p>
		{:else if settings.connection.status === 'expired'}
			<p class="error">Your HoYoLAB login expired. Paste fresh cookie values to reconnect.</p>
		{:else}
			<p>Not connected.</p>
		{/if}
		{#if !showForm}
			<button type="button" onclick={() => (showForm = true)}>Reconnect HoYoLAB</button>
		{:else}
			<ol class="steps">
				<li>Log in at <b>hoyolab.com</b> in your browser.</li>
				<li>Press <b>F12</b> → <b>Application</b> (Firefox: <b>Storage</b>) → <b>Cookies</b> → <code>https://www.hoyolab.com</code>.</li>
				<li>Copy each value below. Only the first two are required. Treat them like a password.</li>
			</ol>
			<form onsubmit={(e) => { e.preventDefault(); submit(); }}>
				{#each FIELDS as f (f.key)}
					<label>
						<span><code>{f.key}</code>{f.required ? ' *' : ''}</span>
						<input type="password" autocomplete="off" bind:value={cookie[f.key]} aria-label={f.key} />
					</label>
				{/each}
				<button class="primary" type="submit" disabled={connecting}>
					{connecting ? 'Testing…' : 'Connect'}
				</button>
			</form>
			{#if connectError}<p class="error">{connectError}</p>{/if}
			{#if accounts}
				<p>This login has several Genshin accounts. Which one?</p>
				{#each accounts as a (a.uid)}
					<button type="button" onclick={() => submit(a.uid)}>
						{a.nickname} · UID {a.uid} · {a.server} · AR {a.level}
					</button>
				{/each}
			{/if}
		{/if}
	</section>

	<section class="panel">
		<h2>Sync</h2>
		<label class="inline">
			Auto-sync when data is older than
			<input type="number" min="1" max="1440" bind:value={interval} aria-label="Sync interval minutes" />
			minutes
		</label>
		<button type="button" onclick={saveInterval}>Save</button>
		{#if savedNote}<span class="muted">{savedNote}</span>{/if}
		<table>
			<thead><tr><th>When</th><th>Trigger</th><th>Roster</th><th>Details</th><th>Notes</th></tr></thead>
			<tbody>
				{#each runs as r (r.id)}
					<tr>
						<td>{timeAgo(r.started_at, now)}</td>
						<td>{r.trigger}</td>
						{#each ['roster', 'details', 'notes'] as p (p)}
							<td title={r.parts[p]?.error ?? ''} class:error={r.parts[p] && !r.parts[p].ok}>
								{#if !r.finished_at}…{:else if !r.parts[p]}—{:else if r.parts[p].ok}ok{:else}failed{/if}
							</td>
						{/each}
					</tr>
				{:else}
					<tr><td colspan="5" class="muted">No syncs yet.</td></tr>
				{/each}
			</tbody>
		</table>
	</section>

	<section class="panel">
		<h2>Default build targets</h2>
		<p class="muted">Used when you set a character to Build for the first time.</p>
		<TargetsEditor targets={settings.default_targets} levelCaps={settings.level_caps} onchange={saveTargets} />
	</section>

	<section class="panel">
		<h2>Game data</h2>
		<p>
			{settings.gamedata.count} characters ·
			{settings.gamedata.fetched_at ? `updated ${timeAgo(settings.gamedata.fetched_at, now)}` : 'never downloaded'}
		</p>
		{#if settings.gamedata.last_error}<p class="error">Last error: {settings.gamedata.last_error}</p>{/if}
		<button type="button" onclick={refreshGamedata} disabled={refreshing}>
			{refreshing ? 'Refreshing…' : 'Refresh game data'}
		</button>
	</section>
{/if}

<style>
	section { margin-bottom: 14px; }
	form { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px; align-items: end; }
	label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--muted); }
	label.inline { flex-direction: row; align-items: center; gap: 8px; display: inline-flex; }
	label.inline input { width: 80px; }
	.steps { color: var(--muted); }
	table { margin-top: 10px; border-collapse: collapse; }
	th, td { text-align: left; padding: 3px 14px 3px 0; font-size: 12px; }
</style>
