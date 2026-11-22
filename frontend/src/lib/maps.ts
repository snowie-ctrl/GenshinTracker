import type { MapKey } from './types';

const KEY = 'gt.lastMap';
const KEYS: MapKey[] = ['hoyolab', 'appsample'];

export function initialTab(stored: string | null, fallback: MapKey): MapKey {
	return KEYS.includes(stored as MapKey) ? (stored as MapKey) : fallback;
}

/** Tablist keyboard: the tab a key moves to (wrapping), or null for keys the tablist ignores. */
export function nextTab<T>(keys: T[], current: T, key: string): T | null {
	const i = keys.indexOf(current);
	if (key === 'ArrowRight') return keys[(i + 1) % keys.length];
	if (key === 'ArrowLeft') return keys[(i - 1 + keys.length) % keys.length];
	if (key === 'Home') return keys[0];
	if (key === 'End') return keys[keys.length - 1];
	return null;
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
