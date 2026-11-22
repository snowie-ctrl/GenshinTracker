<script lang="ts">
	import { onDestroy } from 'svelte';
	import { api, errorMessage } from '$lib/api';
	import { sync } from '$lib/sync.svelte';
	import TargetsEditor from '$lib/TargetsEditor.svelte';
	import { timeAgo } from '$lib/time';
	import type { Account, CacheStatus, MapKey, Settings, SyncRun, Targets } from '$lib/types';
	import { noteTimer } from '$lib/note';
	import { cacheStatusLabel } from '$lib/wishes';
	import GoodImportButton from '$lib/GoodImportButton.svelte';
	import type { GoodStatus } from '$lib/types';
	import { appearance } from '$lib/appearance.svelte';
	import SettingsIndex from '$lib/SettingsIndex.svelte';

	const SECTIONS = [
		{ id: 'account', label: 'Account' },
		{ id: 'sync-data', label: 'Sync & data' },
		{ id: 'appearance', label: 'Appearance' },
		{ id: 'planner', label: 'Planner' },
		{ id: 'wishes', label: 'Wishes' },
		{ id: 'map', label: 'Map' }
	];
	let appearanceNote = $state<string | null>(null);

	async function setBackground(input: HTMLInputElement) {
		appearanceNote = null;
		try {
			await appearance.setBackgroundAnimated(input.checked);
		} catch (e) {
			input.checked = appearance.backgroundAnimated;
			appearanceNote = errorMessage(e);
		}
	}

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

	let good = $state<GoodStatus | null>(null);
	let goodNote = $state<string | null>(null);

	async function loadGood() {
		try {
			good = await api.goodStatus();
		} catch (e) {
			goodNote = errorMessage(e);
		}
	}

	async function setGoodEnabled(on: boolean) {
		try {
			settings = await api.saveSettings({ good_import_enabled: on });
			await loadGood();
		} catch (e) {
			goodNote = errorMessage(e);
		}
	}

	async function deleteGood() {
		if (!confirm('Delete the imported GOOD data? This cannot be undone.')) return;
		try {
			await api.deleteGood();
			await loadGood();
			goodNote = 'Imported data deleted.';
		} catch (e) {
			goodNote = errorMessage(e);
		}
	}

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
		void loadGood();
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
	<div class="layout">
		<SettingsIndex sections={SECTIONS} />
		<div class="groups">
			<section class="panel group" id="account" aria-labelledby="h-account">
				<h2 id="h-account">Account</h2>
				<div class="sub">
					<h3>HoYoLAB</h3>
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
				</div>
			</section>
			<section class="panel group" id="sync-data" aria-labelledby="h-sync-data">
				<h2 id="h-sync-data">Sync &amp; data</h2>
				<div class="sub">
					<h3>Sync</h3>
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
				</div>
				<div class="sub">
					<h3>Game data</h3>
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
						<p>
							{settings.gamedata.artifact_sets.count} artifact sets ·
							{settings.gamedata.artifact_sets.fetched_at ? `updated ${timeAgo(settings.gamedata.artifact_sets.fetched_at, now)}` : 'never downloaded'}
						</p>
						{#if settings.gamedata.artifact_sets.last_error}<p class="error">Artifact sets: {settings.gamedata.artifact_sets.last_error}</p>{/if}
						{#if settings.gamedata.banners.unmapped.length}
							<p class="muted">Banner items not matched to game data: {settings.gamedata.banners.unmapped.join(', ')}</p>
						{/if}
						<button type="button" onclick={refreshGamedata} disabled={refreshing}>
							{refreshing ? 'Refreshing…' : 'Refresh game data'}
						</button>
				</div>
				<div class="sub" data-testid="good-settings">
					<h3>Inventory import (GOOD)</h3>
						<label class="inline">
							<input type="checkbox" checked={settings.good_import_enabled}
								onchange={(e) => setGoodEnabled(e.currentTarget.checked)} />
							Use GOOD inventory import
						</label>
						<p class="muted">The import only reads a file. The scanner that creates it is third-party software, which HoYoverse's terms forbid; use at your own risk.</p>
						{#if good?.imported_at}
							<p>Last import: {new Date(good.imported_at).toLocaleString()}{good.source ? ` from ${good.source}` : ''}
								· {good.counts?.materials.matched ?? 0} materials, {good.counts?.weapons.matched ?? 0} weapons,
								{good.counts?.artifacts.matched ?? 0} artifacts</p>
							{#if good.unmatched.length}<p class="muted">Not recognised: {good.unmatched.join(', ')}</p>{/if}
						{:else}
							<p class="muted">No import yet.</p>
						{/if}
						{#if settings.good_import_enabled}<GoodImportButton onimported={loadGood} />{/if}
						<button type="button" onclick={deleteGood} disabled={!good?.imported_at}>Delete imported data</button>
						{#if goodNote}<span class="muted">{goodNote}</span>{/if}
				</div>
			</section>
			<section class="panel group" id="appearance" aria-labelledby="h-appearance">
				<h2 id="h-appearance">Appearance</h2>
				<div class="sub">
					<label class="inline">
						<input type="checkbox" checked={appearance.backgroundAnimated}
							onchange={(e) => setBackground(e.currentTarget)} />
						Animated background
					</label>
					<p class="muted">Drifting space dust behind every page. It also stays still when your system's reduce-motion setting is on.</p>
					{#if appearanceNote}<span class="error" data-testid="appearance-note">{appearanceNote}</span>{/if}
				</div>
			</section>
			<section class="panel group" id="planner" aria-labelledby="h-planner">
				<h2 id="h-planner">Planner</h2>
				<div class="sub">
					<h3>Default build targets</h3>
						<p class="muted">Used when you set a character to Build for the first time.</p>
						<TargetsEditor targets={settings.default_targets} levelCaps={settings.level_caps} onchange={saveTargets} />
				</div>
			</section>
			<section class="panel group" id="wishes" aria-labelledby="h-wishes">
				<h2 id="h-wishes">Wishes</h2>
				<div class="sub">
						<label>
							Game install path (leave blank to detect it automatically)
							<input type="text" bind:value={gamePath} placeholder="D:\Games\Genshin Impact" />
						</label>
						<button type="button" onclick={saveGamePath}>Save</button>
						{#if gamePathNote}<span class="muted">{gamePathNote}</span>{/if}
						<p class="muted" data-testid="wish-cache">{cache ? cacheStatusLabel(cache, now) : 'Checking the game cache…'}</p>
				</div>
			</section>
			<section class="panel group" id="map" aria-labelledby="h-map">
				<h2 id="h-map">Map</h2>
				<div class="sub">
						<label>
							Default map
							<select aria-label="Default map" value={settings.default_map}
								onchange={(e) => saveDefaultMap(e.currentTarget)}>
								<option value="hoyolab">HoYoLAB Interactive Map</option>
								<option value="appsample">AppSample</option>
							</select>
						</label>
						{#if mapNote}<span class="muted">{mapNote}</span>{/if}
				</div>
			</section>
		</div>
	</div>
{/if}

<style>
	section.group { margin-bottom: 0; }
	form { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px; align-items: end; }
	label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--muted); }
	label.inline { flex-direction: row; align-items: center; gap: 8px; display: inline-flex; }
	label.inline input[type='number'] { width: 80px; }
	.layout { display: grid; grid-template-columns: 200px minmax(0, 1fr); gap: 20px; align-items: start; }
	.groups { display: flex; flex-direction: column; gap: 16px; }
	.group { scroll-margin-top: var(--gutter); margin-bottom: 0; }
	.group > h2 { margin-top: 0; color: var(--cream); }
	.sub + .sub { margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--glass-border); }
	h3 { font-size: 13px; margin: 0 0 8px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }
	@media (max-width: 900px) { .layout { grid-template-columns: 1fr; } }
	.steps { color: var(--muted); }
	table { margin-top: 10px; border-collapse: collapse; }
	th, td { text-align: left; padding: 3px 14px 3px 0; font-size: 12px; }
</style>
