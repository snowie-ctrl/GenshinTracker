import type { CharMaterial, GapStatus, Material } from './types';
import { timeAgo } from './time';

export type InventoryFilter = 'all' | 'needed' | 'farm';
export type Tone = 'short' | 'met' | 'none';
export interface TileView { main: string; badge: string | null; hint: string | null; tone: Tone }

export function tileView(m: Material): TileView {
	if (m.state === 'short') {
		return {
			main: `${m.have ?? 0}/${m.need}`,
			badge: m.to_farm > 0 ? `−${m.to_farm}` : null,
			hint: m.craftable > 0 ? `craft ${m.craftable}` : null,
			tone: 'short'
		};
	}
	if (m.state === 'met') return { main: `✓ ${m.need}`, badge: null, hint: null, tone: 'met' };
	return { main: '', badge: null, hint: null, tone: 'none' };
}

export function charTileView(m: CharMaterial): TileView {
	const hint = m.shared ? 'shared' : null;
	if (m.short > 0) return { main: `${m.need - m.short}/${m.need}`, badge: `−${m.short}`, hint, tone: 'short' };
	return { main: `✓ ${m.need}`, badge: null, hint, tone: 'met' };
}

export function filterMaterials(ms: Material[], filter: InventoryFilter, query: string): Material[] {
	const q = query.trim().toLowerCase();
	return ms.filter((m) => {
		const passes = filter === 'all' ? true : filter === 'needed' ? m.state !== 'unneeded' : m.to_farm > 0;
		return passes && (!q || m.name.toLowerCase().includes(q));
	});
}

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
export function weekdayNames(days: number[]): string {
	return days.map((d) => DAYS[d] ?? '?').join('/');
}

export function gapLabel(g: GapStatus, now: number): string {
	if (g.ok === false) return `⚠ Shortfall update failed: ${g.error ?? 'unknown error'}`;
	if (g.stale) return 'Updating…';
	if (g.computed_at) return `Calculated ${timeAgo(g.computed_at, now)}`;
	return 'Not calculated yet';
}

export function shouldPoll(g: GapStatus | null | undefined): boolean {
	return !!g && g.stale && g.ok !== false;
}
