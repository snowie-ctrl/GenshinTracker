import type { CharMaterial, GapStatus, Material } from './types';
import { timeAgo } from './time';

export type InventoryFilter = 'all' | 'owned';
export type Tone = 'short' | 'met' | 'none';
export interface TileView { main: string; badge: string | null; craft: string | null; hint: string | null; tone: Tone }

export function tileView(m: Material): TileView {
	if (m.state === 'short') {
		return {
			main: `${m.have ?? 0}/${m.need}`,
			badge: m.to_farm > 0 ? `−${m.to_farm}` : null,
			craft: null,
			hint: m.craftable > 0 ? `craft ${m.craftable}` : null,
			tone: 'short'
		};
	}
	if (m.state === 'met') {
		const main = m.scan != null && m.scan >= m.need ? `${m.scan}/${m.need} ✓` : `✓ ${m.need}`;
		return { main, badge: null, craft: null, hint: null, tone: 'met' };
	}
	return { main: m.scan != null ? String(m.scan) : '', badge: null, craft: null, hint: null, tone: 'none' };
}

/** Unneeded tiles are dimmed unless a GOOD scan says you own some. */
export function tileDim(m: Material): boolean {
	return m.state === 'unneeded' && !((m.scan ?? 0) > 0);
}

export function charTileView(m: CharMaterial): TileView {
	const hint = m.shared ? 'shared' : null;
	if (m.short > 0) return { main: `${m.need - m.short}/${m.need}`, badge: `−${m.short}`, craft: null, hint, tone: 'short' };
	return { main: `✓ ${m.need}`, badge: null, craft: null, hint, tone: 'met' };
}

export interface CharMaterialGroup { key: string; label: string; materials: CharMaterial[] }

/** Rows arrive sorted by category; split them into consecutive groups for small headings. */
export function groupByCategory(ms: CharMaterial[]): CharMaterialGroup[] {
	const groups: CharMaterialGroup[] = [];
	for (const m of ms) {
		const last = groups.at(-1);
		if (last && last.key === m.category) last.materials.push(m);
		else groups.push({ key: m.category, label: m.category_label, materials: [m] });
	}
	return groups;
}

export function filterMaterials(ms: Material[], filter: InventoryFilter, query: string): Material[] {
	const q = query.trim().toLowerCase();
	return ms.filter((m) => (filter === 'all' || (m.scan ?? 0) > 0) && (!q || m.name.toLowerCase().includes(q)));
}

export function readInventoryFilter(stored: string | null): InventoryFilter {
	return stored === 'owned' ? 'owned' : 'all';
}

/** Live HoYoLAB count when short (newest), else the GOOD scan, else unknown. */
export function bestKnownCount(m: Material): number | null {
	if (m.state === 'short' && m.have != null) return m.have;
	return m.scan ?? null;
}

export function backpackView(m: Material): TileView {
	const n = bestKnownCount(m);
	return { main: n === null ? '—' : String(n), badge: null, craft: null, hint: null, tone: 'none' };
}

export function backpackDim(m: Material): boolean {
	return !bestKnownCount(m);
}

export function farmView(m: Material): TileView {
	const n = bestKnownCount(m);
	return {
		main: n === null ? '—' : String(n),
		badge: m.to_farm > 0 ? `−${m.to_farm}` : null,
		craft: m.craftable > 0 ? `+${m.craftable}` : null,
		hint: null,
		tone: 'none'
	};
}

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
export function weekdayNames(days: number[]): string {
	return days.map((d) => DAYS[d] ?? '?').join('/');
}

export function gapLabel(g: GapStatus, now: number): string {
	if (g.pending) return 'Updating…';
	if (g.ok === false) return `⚠ Shortfall update failed: ${g.error ?? 'unknown error'}`;
	if (g.stale) return 'Updating…';
	if (g.computed_at) return `Calculated ${timeAgo(g.computed_at, now)}`;
	return 'Not calculated yet';
}

export function shouldPoll(g: GapStatus | null | undefined): boolean {
	return !!g && (g.pending || (g.stale && g.ok !== false));
}

/** A successful calculation exists, so an empty list really means "nothing to farm". */
export function gapsSettled(g: GapStatus): boolean {
	return !!g.computed_at && g.ok !== false;
}

/** For a character (or section) with no calculation behind it, instead of a ✓ empty state. */
export function notCalculatedLabel(g: GapStatus, now: number): string {
	return g.ok === false ? `Not calculated yet · ${gapLabel(g, now)}` : 'Not calculated yet';
}
