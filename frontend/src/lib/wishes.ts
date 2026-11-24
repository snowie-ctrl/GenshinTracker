// frontend/src/lib/wishes.ts
import { timeAgo } from './time';
import type { CacheStatus, Fate, HistoryFilters, Luck, MonthRow, Outcome, PityLine, Pool, Radiance, Rotation, TierCounts, WishFilter, WishImport } from './types';

export const POOLS: Pool[] = ['character', 'weapon', 'chronicled', 'standard', 'beginner'];
export const POOL_LABEL: Record<Pool, string> = {
	character: 'Character Event', weapon: 'Weapon Event', chronicled: 'Chronicled Wish',
	standard: 'Standard', beginner: "Beginners' Wish"
};
const POOL_SHORT: Record<Pool, string> = {
	character: 'Character', weapon: 'Weapon', chronicled: 'Chronicled', standard: 'Standard', beginner: 'Beginner'
};
export const POOL_COLOR: Record<Pool, string> = {
	character: 'var(--wanted)', weapon: 'var(--obtained)', chronicled: 'var(--building)',
	standard: 'var(--muted)', beginner: 'var(--unobtained)'
};
const OUTCOME: Record<Outcome, string> = {
	won: 'Won', lost: 'Lost', guaranteed: 'Guaranteed', unknown: 'Unknown', charted: 'Charted', not_charted: 'Not charted'
};
const NEXT: Record<string, string> = {
	'50/50': 'Next 5★: 50/50', '75/25': 'Next 5★: 75/25', guaranteed: 'Next 5★: guaranteed featured',
	unknown: 'Next 5★: unknown (import older history)'
};

export function outcomeLabel(o: Outcome | null): string {
	return o ? OUTCOME[o] : '';
}

export function nextStateLabel(s: string | null): string {
	return s ? (NEXT[s] ?? '') : '';
}

export function pityBar(pity: number, hard: number, soft: number | null, avg: number | null = null):
	{ fill: number; soft: number | null; avg: number | null } {
	const pct = (n: number) => Math.round((n / hard) * 1000) / 10;
	return {
		fill: Math.min(100, Math.max(0, pct(pity))), soft: soft === null ? null : pct(soft),
		avg: avg === null ? null : Math.min(100, pct(avg))
	};
}

export function fateLine(f: Fate | null, pool: Pool): string {
	if (!f) return '';
	if (f.points === null) {
		if (f.choices.length === 0) return 'No banner is running right now';
		return `Pick your charted ${pool === 'weapon' ? 'weapon' : 'item'} to track fate points`;
	}
	return f.points >= 1
		? `Fate point 1/1 → next 5★ is ${f.chart_name}`
		: `Fate point 0/1 · charted ${f.chart_name}`;
}

export function radianceLine(r: Radiance | null): string {
	if (!r) return '';
	const base = `Lost 50/50s in a row: ${r.losses ?? 'unknown'} (estimate)`;
	return r.likely ? `${base} · Capturing Radiance likely on your next 50/50` : base;
}

export function importResultLine(last: WishImport | null): string {
	if (!last) return 'No imports yet';
	if (last.ok === null) return 'Importing…';
	if (!last.ok) return last.error ?? 'Import failed';
	if (!last.added && !last.upgraded) return 'No new pulls';
	return `+${last.added} new` + (last.upgraded ? ` · ${last.upgraded} upgraded` : '');
}

export function cacheStatusLabel(st: CacheStatus, now: number): string {
	switch (st.status) {
		case 'found':
			return st.cached_at ? `Wish link found (cached ${timeAgo(st.cached_at, now)})` : 'Wish link found';
		case 'no_link':
			return 'No wish link in the cache: open Wish History in-game';
		case 'locked':
			return 'Game is running (cache locked)';
		default:
			return 'Game cache not found';
	}
}

export function pityLine(l: PityLine): string {
	const state = l.next_state === 'guaranteed' ? ' · Guaranteed'
		: l.next_state === '50/50' || l.next_state === '75/25' ? ` · ${l.next_state}` : '';
	const fate = l.fate_points === null ? '' : ` · Fate ${l.fate_points}/1`;
	return `${POOL_SHORT[l.pool]} ${l.pity5}/${l.hard}${state}${fate}`;
}

export function scaleTo(values: number[], size: number): number[] {
	const max = Math.max(0, ...values);
	return values.map((v) => (max ? Math.round((v / max) * size * 10) / 10 : 0));
}

export function niceMax(n: number): number {
	if (n <= 0) return 0;
	const p = 10 ** Math.floor(Math.log10(n));
	for (const m of [1, 2, 5, 10]) if (m * p >= n) return m * p;
	return 10 * p;
}

export type Bar = { label: string; segments: { name: string; value: number; color: string }[] };

export function stackedMonths(rows: MonthRow[]): Bar[] {
	return rows.map((r) => ({
		label: `${r.month.slice(5, 7)}/${r.month.slice(2, 4)}`,
		segments: POOLS.map((p) => ({ name: POOL_LABEL[p], value: r[p], color: POOL_COLOR[p] }))
	}));
}

export function histogramBars(buckets: { bucket: string; count: number }[]): Bar[] {
	return buckets.map((b) => ({ label: b.bucket, segments: [{ name: '5★', value: b.count, color: 'var(--wanted)' }] }));
}

export const DEFAULT_FILTERS: HistoryFilters = { pool: '', rarity: '', type: '', banner: '', q: '' };
const FILTER_KEY = 'wishes.historyFilters';

export function historyQuery(f: HistoryFilters, page: number): string {
	const params = new URLSearchParams();
	if (f.pool) params.set('pool', f.pool);
	if (f.rarity !== '') params.set('rarity', String(f.rarity));
	if (f.type) params.set('type', f.type);
	if (f.banner) params.set('banner', f.banner);
	if (f.q.trim()) params.set('q', f.q.trim());
	params.set('page', String(page));
	return params.toString();
}

export function loadFilters(storage: () => Storage): HistoryFilters {
	try {
		const raw = storage().getItem(FILTER_KEY);
		return raw ? { ...DEFAULT_FILTERS, ...JSON.parse(raw) } : { ...DEFAULT_FILTERS };
	} catch {
		return { ...DEFAULT_FILTERS };
	}
}

export function saveFilters(storage: () => Storage, f: HistoryFilters): void {
	try {
		storage().setItem(FILTER_KEY, JSON.stringify(f));
	} catch {
		/* storage unavailable: filters just aren't remembered */
	}
}

export const FILTER_ORDER: WishFilter[] = ['all', 'character', 'weapon', 'chronicled', 'standard'];
export const FILTER_LABEL: Record<WishFilter, string> = {
	all: 'All banners', character: 'Character Event', weapon: 'Weapon Event', chronicled: 'Chronicled Wish',
	standard: 'Standard'
};

export function availableFilters(analysis: Partial<Record<WishFilter, unknown>>): WishFilter[] {
	return FILTER_ORDER.filter((f) => f in analysis);
}

export function pickFilter(saved: string | null, available: WishFilter[]): WishFilter {
	if (saved && (available as string[]).includes(saved)) return saved as WishFilter;
	if (available.includes('character')) return 'character';
	return available.find((f) => f !== 'all') ?? 'all';
}

export function toFilter(pool: Pool): WishFilter {
	return pool === 'beginner' ? 'all' : pool;
}

const WISH_FILTER_KEY = 'wishes.filter';

export function loadWishFilter(): string | null {
	try {
		return localStorage.getItem(WISH_FILTER_KEY);
	} catch {
		return null;
	}
}

export function saveWishFilter(f: WishFilter): void {
	try {
		localStorage.setItem(WISH_FILTER_KEY, f);
	} catch {
		/* storage unavailable: the filter just is not remembered */
	}
}

export function rotationBars(rows: Rotation[]): Bar[] {
	return rows.map((r) => ({
		label: r.label,
		segments: POOLS.map((p) => ({ name: POOL_LABEL[p], value: r.pool_counts[p] ?? 0, color: POOL_COLOR[p] }))
	}));
}

export function spiderSeries(t: TierCounts, axes: readonly string[]): { five: number[]; four: number[] } {
	return { five: axes.map((a) => t.five[a] ?? 0), four: axes.map((a) => t.four[a] ?? 0) };
}

export function verdictLabel(v: Luck['verdict']): string {
	if (v === 'luckier') return 'Luckier than average';
	if (v === 'unluckier') return 'Unluckier than average';
	if (v === 'average') return 'About average';
	return '';
}
