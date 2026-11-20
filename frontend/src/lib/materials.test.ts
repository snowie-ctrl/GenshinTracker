import { describe, expect, it } from 'vitest';
import type { CharMaterial, GapStatus, Material } from './types';
import {
	charTileView, filterMaterials, gapLabel, gapsSettled, groupByCategory, notCalculatedLabel, shouldPoll, tileView,
	weekdayNames
} from './materials';

function m(over: Partial<Material>): Material {
	return {
		id: 1, name: 'Guide to Freedom', icon: 'UI_ItemIcon_1', rarity: 3, category: 'talent', state: 'unneeded',
		need: 0, short: 0, have: null, craftable: 0, to_farm: 0, sources: [], characters: [], ...over
	};
}
const gaps = (over: Partial<GapStatus>): GapStatus =>
	({ computed_at: null, ok: null, error: null, stale: false, pending: false, skipped: [], ...over });

describe('tileView', () => {
	it('short shows have/need, to-farm badge and craft hint', () => {
		expect(tileView(m({ state: 'short', need: 18, short: 7, have: 11, to_farm: 4, craftable: 3 })))
			.toEqual({ main: '11/18', badge: '−4', hint: 'craft 3', tone: 'short' });
	});
	it('short fully covered by crafting has no badge', () => {
		expect(tileView(m({ state: 'short', need: 5, short: 2, have: 3, to_farm: 0, craftable: 2 })).badge).toBeNull();
	});
	it('met and unneeded', () => {
		expect(tileView(m({ state: 'met', need: 24 }))).toEqual({ main: '✓ 24', badge: null, hint: null, tone: 'met' });
		expect(tileView(m({}))).toEqual({ main: '', badge: null, hint: null, tone: 'none' });
	});
});

describe('charTileView', () => {
	const c = (over: Partial<CharMaterial>): CharMaterial =>
		({ id: 1, name: 'x', icon: 'i', rarity: 3, category: 'talent', category_label: 'Talent books', need: 9, short: 0, shared: false, ...over });
	it('short with shared mark', () => {
		expect(charTileView(c({ short: 4, shared: true }))).toEqual({ main: '5/9', badge: '−4', hint: 'shared', tone: 'short' });
	});
	it('met', () => {
		expect(charTileView(c({}))).toEqual({ main: '✓ 9', badge: null, hint: null, tone: 'met' });
	});
});

describe('filterMaterials', () => {
	const list = [m({ id: 1, state: 'unneeded', name: 'Mora' }), m({ id: 2, state: 'met', need: 3, name: 'Hero' }),
		m({ id: 3, state: 'short', need: 3, short: 1, to_farm: 1, name: 'Guide' }),
		m({ id: 4, state: 'short', need: 3, short: 1, to_farm: 0, craftable: 1, name: 'Philosophies' })];
	it('all / needed / farm', () => {
		expect(filterMaterials(list, 'all', '').map((x) => x.id)).toEqual([1, 2, 3, 4]);
		expect(filterMaterials(list, 'needed', '').map((x) => x.id)).toEqual([2, 3, 4]);
		expect(filterMaterials(list, 'farm', '').map((x) => x.id)).toEqual([3]);
	});
	it('search is case-insensitive', () => {
		expect(filterMaterials(list, 'all', 'gUiD').map((x) => x.id)).toEqual([3]);
	});
});

describe('labels', () => {
	it('weekday names', () => expect(weekdayNames([0, 3, 6])).toBe('Mon/Thu/Sun'));
	it('gap label priorities', () => {
		expect(gapLabel(gaps({ ok: false, error: 'boom', stale: true, pending: true }), 0)).toBe('Updating…');
		expect(gapLabel(gaps({ ok: false, error: 'boom', stale: true }), 0)).toBe('⚠ Shortfall update failed: boom');
		expect(gapLabel(gaps({ stale: true }), 0)).toBe('Updating…');
		expect(gapLabel(gaps({}), 0)).toBe('Not calculated yet');
		expect(gapLabel(gaps({ computed_at: new Date(0).toISOString() }), 60_000)).toContain('Calculated');
	});
	it('polls while pending, or stale and not failed', () => {
		expect(shouldPoll(gaps({ stale: true }))).toBe(true);
		expect(shouldPoll(gaps({ stale: true, ok: false }))).toBe(false);
		expect(shouldPoll(gaps({ stale: true, ok: false, pending: true }))).toBe(true);
		expect(shouldPoll(gaps({ ok: false, pending: true }))).toBe(true);
		expect(shouldPoll(gaps({}))).toBe(false);
		expect(shouldPoll(null)).toBe(false);
	});
	it('settled only after a successful calculation', () => {
		const at = new Date(0).toISOString();
		expect(gapsSettled(gaps({}))).toBe(false);
		expect(gapsSettled(gaps({ computed_at: at, ok: true }))).toBe(true);
		expect(gapsSettled(gaps({ computed_at: at, ok: false, error: 'boom' }))).toBe(false);
	});
	it('groups shortfall rows by category, keeping order', () => {
		const row = (id: number, category: string, category_label: string): CharMaterial =>
			({ id, name: `M${id}`, icon: '', rarity: 3, category, category_label, need: 1, short: 1, shared: false });
		const groups = groupByCategory([row(1, 'talent', 'Talent books'), row(2, 'talent', 'Talent books'),
			row(3, 'weekly', 'Weekly boss drops')]);
		expect(groups.map((g) => [g.key, g.label, g.materials.map((m) => m.id)])).toEqual([
			['talent', 'Talent books', [1, 2]], ['weekly', 'Weekly boss drops', [3]]
		]);
		expect(groupByCategory([])).toEqual([]);
	});
	it('not calculated label adds the failure', () => {
		expect(notCalculatedLabel(gaps({}), 0)).toBe('Not calculated yet');
		expect(notCalculatedLabel(gaps({ stale: true }), 0)).toBe('Not calculated yet');
		expect(notCalculatedLabel(gaps({ ok: false, error: 'boom' }), 0))
			.toBe('Not calculated yet · ⚠ Shortfall update failed: boom');
	});
});
