<script lang="ts">
	import { onDestroy } from 'svelte';
	import { api, errorMessage } from '$lib/api';
	import { sync } from '$lib/sync.svelte';
	import TargetsEditor from '$lib/TargetsEditor.svelte';
	import { timeAgo } from '$lib/time';
	import type { Account, CacheStatus, MapKey, Settings, SyncRun, Targets } from '$lib/types';
	import { noteTimer } from '$lib/note';
	import { cacheStatusLabel } from '$lib/wishes';

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
	let gamePath = $state('');
	let gamePathLoaded = false;
	let gamePathNote = $state<string | null>(null);
	let cache = $state<CacheStatus | null>(null);
	let mapNote = $state<string | null>(null);
	const intervalNotes = noteTimer((v) => (savedNote = v));
	const gamePathNotes = noteTimer((v) => (gamePathNote = v));
	const mapNotes = noteTimer((v) => (mapNote = v));
	onDestroy(() => [intervalNotes, gamePathNotes, mapNotes].forEach((n) => n.cancel()));

	async function loadCache() {
		try {
			cache = await api.cacheStatus();
		} catch {
			cache = null;
		}
	}

	async function saveGamePath() {
		try {
			settings = await api.saveSettings({ game_install_path: gamePath });
			gamePath = settings.game_install_path;
			gamePathNotes.saved();
			await loadCache();
		} catch (e) {
			gamePathNotes.error(errorMessage(e));
		}
	}

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
			if (!gamePathLoaded) {
				gamePath = s.game_install_path;
				gamePathLoaded = true;
			}
			showForm = showForm || s.connection.status !== 'connected';
			error = null;
		} catch (e) {
			error = errorMessage(e);
		}
		void loadCache();
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
			intervalNotes.saved();
		} catch (e) {
			intervalNotes.error(errorMessage(e));
		}
	}

	async function saveDefaultMap(select: HTMLSelectElement) {
		try {
			settings = await api.saveSettings({ default_map: select.value as MapKey });
			mapNotes.saved();
		} catch (e) {
			// the saved value didn't change, so the select would keep showing the rejected choice
			if (settings) select.value = settings.default_map;
			mapNotes.error(errorMessage(e));
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
			<thead><tr><th>When</th><th>Trigger</th><th>Roster</th><th>Details</th><th>Notes</th><th>Calendar</th><th>Profile</th><th>Challenges</th></tr></thead>
			<tbody>
				{#each runs as r (r.id)}
					<tr>
						<td>{timeAgo(r.started_at, now)}</td>
						<td>{r.trigger}</td>
						{#each ['roster', 'details', 'notes', 'calendar', 'profile', 'challenges'] as p (p)}
							<td title={r.parts[p]?.error ?? ''} class:error={r.parts[p] && !r.parts[p].ok}>
								{#if !r.finished_at}…{:else if !r.parts[p]}—{:else if r.parts[p].skipped}fresh{:else if r.parts[p].ok}ok{:else}failed{/if}
							</td>
						{/each}
					</tr>
				{:else}
					<tr><td colspan="8" class="muted">No syncs yet.</td></tr>
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
		<h2>Wishes</h2>
		<label>
			Game install path (leave blank to detect it automatically)
			<input type="text" bind:value={gamePath} placeholder="D:\Games\Genshin Impact" />
		</label>
		<button type="button" onclick={saveGamePath}>Save</button>
		{#if gamePathNote}<span class="muted">{gamePathNote}</span>{/if}
		<p class="muted" data-testid="wish-cache">{cache ? cacheStatusLabel(cache, now) : 'Checking the game cache…'}</p>
	</section>

	<section class="panel">
		<h2>Map</h2>
		<label>
			Default map
			<select aria-label="Default map" value={settings.default_map}
				onchange={(e) => saveDefaultMap(e.currentTarget)}>
				<option value="hoyolab">HoYoLAB Interactive Map</option>
				<option value="appsample">AppSample</option>
			</select>
		</label>
		{#if mapNote}<span class="muted">{mapNote}</span>{/if}
	</section>

	<section class="panel">
		<h2>Game data</h2>
		<p>
			{settings.gamedata.count} characters ·
			{settings.gamedata.fetched_at ? `updated ${timeAgo(settings.gamedata.fetched_at, now)}` : 'never downloaded'}
		</p>
		{#if settings.gamedata.last_error}<p class="error">Last error: {settings.gamedata.last_error}</p>{/if}
		<p>
			{settings.gamedata.materials.count} materials ·
			{settings.gamedata.materials.fetched_at ? `updated ${timeAgo(settings.gamedata.materials.fetched_at, now)}` : 'never downloaded'}
		</p>
		{#if settings.gamedata.materials.last_error}<p class="error">Materials: {settings.gamedata.materials.last_error}</p>{/if}
		<p>
			{settings.gamedata.banners.count} banners ·
			{settings.gamedata.banners.fetched_at ? `updated ${timeAgo(settings.gamedata.banners.fetched_at, now)}` : 'never downloaded'}
		</p>
		{#if settings.gamedata.banners.last_error}<p class="error">Banners: {settings.gamedata.banners.last_error}</p>{/if}
		{#if settings.gamedata.banners.unmapped.length}
			<p class="muted">Banner items not matched to game data: {settings.gamedata.banners.unmapped.join(', ')}</p>
		{/if}
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
