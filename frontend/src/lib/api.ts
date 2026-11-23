import type {
	DeleteTeamResponse,
	BannerHistoryPage, EventsResponse, CacheStatus, Character, CharacterDetail, ConnectResponse, Dashboard, Goal, HistoryFilters, HistoryPage,
	GoodArtifact, GoodStatus, GoodSummary, GoodWeapon, ImportStatus, Inventory, MapKey, MapsResponse, Pool, PoolSummary, PriorityResult, ProfileResponse, SaveTeamResponse, Settings, SyncStatus, Tag, TagWithCount, Targets,
	Talents, TeamBody, TeamResponse, TeamsResponse, TravelerInfo, WeaponOption, WishSummary
} from './types';
import { historyQuery } from './wishes';

export class ApiError extends Error {
	constructor(public status: number, message: string) {
		super(message);
	}
}

async function parse<T>(res: Response): Promise<T> {
	if (!res.ok) {
		let message = res.statusText;
		try {
			const j = await res.json();
			message = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail);
		} catch {
			/* keep statusText */
		}
		throw new ApiError(res.status, message);
	}
	if (res.status === 204) return undefined as T;
	return (await res.json()) as T;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
	return parse<T>(await fetch(`/api${path}`, {
		method,
		headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
		body: body === undefined ? undefined : JSON.stringify(body)
	}));
}

async function upload<T>(path: string, file: File): Promise<T> {
	const form = new FormData();
	form.append('file', file);
	return parse<T>(await fetch(`/api${path}`, { method: 'POST', body: form }));
}

export const api = {
	characters: () => request<Character[]>('GET', '/characters'),
	character: (slug: string) => request<CharacterDetail>('GET', `/characters/${encodeURIComponent(slug)}`),
	setTraveler: (id: number, body: { unlocked?: boolean; talents?: Talents; constellation?: number }) =>
		request<TravelerInfo>('PUT', `/traveler/${id}`, body),
	setGoal: (id: number, body: { goal?: Goal; targets?: Targets; planned_weapon_id?: number | null }) =>
		request<Character>('PUT', `/characters/${id}/goal`, body),
	inventory: () => request<Inventory>('GET', '/inventory'),
	weapons: (type: string) => request<WeaponOption[]>('GET', `/weapons?type=${encodeURIComponent(type)}`),
	setBossDone: (name: string, done: boolean) =>
		request<{ name: string; done: boolean }>('PUT', `/weekly-bosses/${encodeURIComponent(name)}`, { done }),
	dashboard: () => request<Dashboard>('GET', '/dashboard'),
	setPriority: (order: number[]) => request<PriorityResult>('PUT', '/priority', { order }),
	profile: () => request<ProfileResponse>('GET', '/profile'),
	settings: () => request<Settings>('GET', '/settings'),
	saveSettings: (body: { sync_interval_minutes?: number; default_targets?: Targets; game_install_path?: string; default_map?: MapKey; good_import_enabled?: boolean; background_animated?: boolean; display_name?: string }) =>
		request<Settings>('PUT', '/settings', body),
	goodStatus: () => request<GoodStatus>('GET', '/good/status'),
	importGood: (file: File) => upload<GoodSummary>('/good/import', file),
	deleteGood: () => request<void>('DELETE', '/good'),
	goodWeapons: () => request<GoodWeapon[]>('GET', '/good/weapons'),
	goodArtifacts: () => request<GoodArtifact[]>('GET', '/good/artifacts'),
	maps: () => request<MapsResponse>('GET', '/map'),
	connect: (body: Record<string, string | number>) =>
		request<ConnectResponse>('POST', '/settings/hoyolab', body),
	refreshGamedata: () => request<{ refreshed: boolean }>('POST', '/gamedata/refresh'),
	startSync: (trigger: 'auto' | 'manual') =>
		request<{ run_id: number | null; started: boolean; reason: string }>('POST', `/sync?trigger=${trigger}`),
	syncStatus: () => request<SyncStatus>('GET', '/sync/status'),
	wishSummary: () => request<WishSummary>('GET', '/wishes/summary'),
	wishHistory: (f: HistoryFilters, page: number) => request<HistoryPage>('GET', `/wishes?${historyQuery(f, page)}`),
	importStatus: () => request<ImportStatus>('GET', '/wishes/import/status'),
	importGame: () => request<{ import_id: number }>('POST', '/wishes/import/game'),
	uploadWishes: (file: File) => upload<ImportStatus>('/wishes/import/file', file),
	setChart: (pool: Pool, item_id: number | null) => request<PoolSummary>('PUT', `/wishes/chart/${pool}`, { item_id }),
	cacheStatus: () => request<CacheStatus>('GET', '/wishes/cache-status'),
	teams: () => request<TeamsResponse>('GET', '/teams'),
	team: (id: number) => request<TeamResponse>('GET', `/teams/${id}`),
	createTeam: (body: TeamBody) => request<SaveTeamResponse>('POST', '/teams', body),
	updateTeam: (id: number, body: TeamBody) => request<SaveTeamResponse>('PUT', `/teams/${id}`, body),
	deleteTeam: (id: number) => request<DeleteTeamResponse>('DELETE', `/teams/${id}`),
	setTeamBuild: (id: number, on: boolean) => request<SaveTeamResponse>('PUT', `/teams/${id}/build`, { on }),
	reorderTeams: (ids: number[]) => request<{ ok: boolean }>('PUT', '/teams/order', { ids }),
	tags: () => request<TagWithCount[]>('GET', '/tags'),
	createTag: (name: string, color?: string) => request<Tag>('POST', '/tags', { name, color }),
	updateTag: (id: number, patch: { name?: string; color?: string }) => request<Tag>('PUT', `/tags/${id}`, patch),
	deleteTag: (id: number) => request<{ ok: boolean }>('DELETE', `/tags/${id}`),
	events: () => request<EventsResponse>('GET', '/events'),
	setEventDone: (id: number, done: boolean) => request<{ id: number; done: boolean }>('PUT', `/events/${id}/done`, { done }),
	bannerHistory: (pool: string, q: string, page: number) =>
		request<BannerHistoryPage>('GET', `/banners/history?pool=${encodeURIComponent(pool)}&q=${encodeURIComponent(q)}&page=${page}`)
};

export function errorMessage(e: unknown): string {
	return e instanceof Error ? e.message : String(e);
}
