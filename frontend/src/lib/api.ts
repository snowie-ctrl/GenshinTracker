import type {
	Character, CharacterDetail, ConnectResponse, Dashboard, Goal, Inventory, Settings, SyncStatus, Targets,
	WeaponOption
} from './types';

export class ApiError extends Error {
	constructor(public status: number, message: string) {
		super(message);
	}
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
	const res = await fetch(`/api${path}`, {
		method,
		headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
		body: body === undefined ? undefined : JSON.stringify(body)
	});
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
	return (await res.json()) as T;
}

export const api = {
	characters: () => request<Character[]>('GET', '/characters'),
	character: (slug: string) => request<CharacterDetail>('GET', `/characters/${encodeURIComponent(slug)}`),
	setGoal: (id: number, body: { goal?: Goal; targets?: Targets; planned_weapon_id?: number | null }) =>
		request<Character>('PUT', `/characters/${id}/goal`, body),
	inventory: () => request<Inventory>('GET', '/inventory'),
	weapons: (type: string) => request<WeaponOption[]>('GET', `/weapons?type=${encodeURIComponent(type)}`),
	setBossDone: (name: string, done: boolean) =>
		request<{ name: string; done: boolean }>('PUT', `/weekly-bosses/${encodeURIComponent(name)}`, { done }),
	dashboard: () => request<Dashboard>('GET', '/dashboard'),
	settings: () => request<Settings>('GET', '/settings'),
	saveSettings: (body: { sync_interval_minutes?: number; default_targets?: Targets }) =>
		request<Settings>('PUT', '/settings', body),
	connect: (body: Record<string, string | number>) =>
		request<ConnectResponse>('POST', '/settings/hoyolab', body),
	refreshGamedata: () => request<{ refreshed: boolean }>('POST', '/gamedata/refresh'),
	startSync: (trigger: 'auto' | 'manual') =>
		request<{ run_id: number | null; started: boolean; reason: string }>('POST', `/sync?trigger=${trigger}`),
	syncStatus: () => request<SyncStatus>('GET', '/sync/status')
};

export function errorMessage(e: unknown): string {
	return e instanceof Error ? e.message : String(e);
}
