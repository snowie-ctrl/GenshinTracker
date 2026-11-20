import type { Status } from './types';

const KEY = 'gt.collapsed';
const DEFAULTS: Record<Status, boolean> = { building: false, obtained: false, wanted: false, unobtained: true };

export function loadCollapsed(): Record<Status, boolean> {
	try {
		const raw = localStorage.getItem(KEY);
		if (raw) return { ...DEFAULTS, ...JSON.parse(raw) };
	} catch {
		/* storage blocked or corrupt: use defaults */
	}
	return { ...DEFAULTS };
}

export function saveCollapsed(value: Record<Status, boolean>): void {
	try {
		localStorage.setItem(KEY, JSON.stringify(value));
	} catch {
		/* ignore */
	}
}
