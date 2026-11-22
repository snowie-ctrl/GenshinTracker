import type { MapKey } from './types';

const KEY = 'gt.lastMap';
const KEYS: MapKey[] = ['hoyolab', 'appsample'];

export function initialTab(stored: string | null, fallback: MapKey): MapKey {
	return KEYS.includes(stored as MapKey) ? (stored as MapKey) : fallback;
}

export function loadLastMap(): string | null {
	try {
		return localStorage.getItem(KEY);
	} catch {
		return null;
	}
}

export function saveLastMap(key: MapKey): void {
	try {
		localStorage.setItem(KEY, key);
	} catch {
		/* ignore */
	}
}
