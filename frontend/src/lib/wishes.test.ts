// frontend/src/lib/wishes.test.ts
import { describe, expect, it } from 'vitest';
import type { Fate, WishImport } from './types';
import {
	DEFAULT_FILTERS, availableFilters, cacheStatusLabel, fateLine, histogramBars, historyQuery, importResultLine,
	loadFilters, nextStateLabel, niceMax, outcomeLabel, pickFilter, pityBar, pityLine, radianceLine, rotationBars,
	saveFilters, scaleTo, spiderSeries, stackedMonths, toFilter, verdictLabel
} from './wishes';

const fate = (p: Partial<Fate>): Fate => ({
	points: null, max: 1, chart_item_id: null, chart_name: null,
	choices: [{ item_id: 1, name: 'Mistsplitter Reforged' }], banner: 'Mist', ...p
});
const imp = (p: Partial<WishImport>): WishImport => ({
	id: 1, source: 'game', started_at: '2024-01-01T00:00:00Z', finished_at: '2024-01-01T00:01:00Z',
	ok: true, added: 0, upgraded: 0, skipped: 0, error: null, ...p
});

describe('labels', () => {
	it('outcomes and next state', () => {
		expect(outcomeLabel('won')).toBe('Won');
		expect(outcomeLabel('not_charted')).toBe('Not charted');
		expect(outcomeLabel(null)).toBe('');
		expect(nextStateLabel('guaranteed')).toBe('Next 5★: guaranteed featured');
		expect(nextStateLabel('75/25')).toBe('Next 5★: 75/25');
		expect(nextStateLabel(null)).toBe('');
	});
	it('fate line', () => {
		expect(fateLine(fate({}), 'weapon')).toBe('Pick your charted weapon to track fate points');
		expect(fateLine(fate({}), 'chronicled')).toBe('Pick your charted item to track fate points');
		expect(fateLine(fate({ choices: [] }), 'weapon')).toBe('No banner is running right now');
		expect(fateLine(fate({ points: 1, chart_item_id: 1, chart_name: 'Mistsplitter Reforged' }), 'weapon'))
			.toBe('Fate point 1/1 → next 5★ is Mistsplitter Reforged');
		expect(fateLine(fate({ points: 0, chart_item_id: 1, chart_name: 'Mistsplitter Reforged' }), 'weapon'))
			.toBe('Fate point 0/1 · charted Mistsplitter Reforged');
	});
	it('radiance line', () => {
		expect(radianceLine({ losses: 2, likely: true, estimate: true }))
			.toBe('Lost 50/50s in a row: 2 (estimate) · Capturing Radiance likely on your next 50/50');
		expect(radianceLine({ losses: null, likely: null, estimate: true })).toBe('Lost 50/50s in a row: unknown (estimate)');
	});
	it('import result line', () => {
		expect(importResultLine(null)).toBe('No imports yet');
		expect(importResultLine(imp({ added: 37, upgraded: 2 }))).toBe('+37 new · 2 upgraded');
		expect(importResultLine(imp({}))).toBe('No new pulls');
		expect(importResultLine(imp({ ok: false, error: 'Close Genshin Impact and try again.' })))
			.toBe('Close Genshin Impact and try again.');
		expect(importResultLine(imp({ ok: null }))).toBe('Importing…');
	});
	it('cache status label', () => {
		const now = Date.parse('2024-01-01T03:00:00Z');
		expect(cacheStatusLabel({ status: 'found', cached_at: '2024-01-01T00:00:00Z' }, now)).toBe('Wish link found (cached 3 h ago)');
		expect(cacheStatusLabel({ status: 'locked', cached_at: null }, now)).toBe('Game is running (cache locked)');
	});
	it('dashboard pity line', () => {
		expect(pityLine({ pool: 'character', pity5: 42, hard: 90, next_state: 'guaranteed', fate_points: null }))
			.toBe('Character 42/90 · Guaranteed');
		expect(pityLine({ pool: 'weapon', pity5: 12, hard: 80, next_state: '75/25', fate_points: 1 }))
			.toBe('Weapon 12/80 · 75/25 · Fate 1/1');
	});
});

describe('numbers', () => {
	it('pity bar marks', () => {
		expect(pityBar(45, 90, 74)).toEqual({ fill: 50, soft: 82.2, avg: null });
		expect(pityBar(120, 90, null)).toEqual({ fill: 100, soft: null, avg: null });
		expect(pityBar(10, 90, 74, 62.3)).toEqual({ fill: 11.1, soft: 82.2, avg: 69.2 });
	});
	it('scales and nice maxima', () => {
		expect(scaleTo([0, 5, 10], 100)).toEqual([0, 50, 100]);
		expect(scaleTo([0, 0], 100)).toEqual([0, 0]);
		expect([niceMax(0), niceMax(7), niceMax(13), niceMax(260)]).toEqual([0, 10, 20, 500]);
	});
	it('stacked months and histogram bars', () => {
		const bars = stackedMonths([{ month: '2024-01', character: 3, weapon: 1, chronicled: 0, standard: 0, beginner: 0 }]);
		expect(bars[0].label).toBe('01/24');
		expect(bars[0].segments.map((s) => [s.name, s.value])).toEqual([
			['Character Event', 3], ['Weapon Event', 1], ['Chronicled Wish', 0], ['Standard', 0], ["Beginners' Wish", 0]
		]);
		expect(histogramBars([{ bucket: '1-10', count: 2 }])[0]).toEqual({
			label: '1-10', segments: [{ name: '5★', value: 2, color: 'var(--wanted)' }]
		});
	});
});

describe('history filters', () => {
	it('builds a query without empty values', () => {
		expect(historyQuery(DEFAULT_FILTERS, 1)).toBe('page=1');
		expect(historyQuery({ pool: 'weapon', rarity: 5, type: '', banner: '', q: 'mist' }, 2))
			.toBe('pool=weapon&rarity=5&q=mist&page=2');
	});
	it('survives unavailable storage', () => {
		const broken = () => { throw new Error('denied'); };
		expect(loadFilters(broken)).toEqual(DEFAULT_FILTERS);
		expect(() => saveFilters(broken, DEFAULT_FILTERS)).not.toThrow();
		const store = new Map<string, string>();
		const fake = () => ({ getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => void store.set(k, v) }) as unknown as Storage;
		saveFilters(fake, { ...DEFAULT_FILTERS, rarity: 5 });
		expect(loadFilters(fake).rarity).toBe(5);
	});
});

describe('wish filters and analysis helpers', () => {
	it('lists filters in a fixed order and picks a sensible default', () => {
		const avail = availableFilters({ standard: {}, all: {}, character: {} });
		expect(avail).toEqual(['all', 'character', 'standard']);
		expect(pickFilter(null, avail)).toBe('character');
		expect(pickFilter('standard', avail)).toBe('standard');
		expect(pickFilter('weapon', avail)).toBe('character');          // remembered filter without pulls
		expect(pickFilter(null, ['all', 'standard'])).toBe('standard');
		expect(pickFilter(null, [])).toBe('all');
		expect(toFilter('beginner')).toBe('all');
		expect(toFilter('weapon')).toBe('weapon');
	});
	it('stacks rotation bars by pool', () => {
		const [bar] = rotationBars([{ label: '4.3 ph1', version: '4.3', start: '2024-01-10 06:00:00',
			pool_counts: { character: 3, standard: 1 }, pulls: 4, fives: [] }]);
		expect(bar.label).toBe('4.3 ph1');
		expect(bar.segments.find((s) => s.name === 'Character Event')?.value).toBe(3);
		expect(bar.segments.find((s) => s.name === 'Weapon Event')?.value).toBe(0);
	});
	it('reads spider series in axis order and labels verdicts', () => {
		expect(spiderSeries({ five: { Hydro: 2 }, four: { Pyro: 1 } }, ['Pyro', 'Hydro']))
			.toEqual({ five: [0, 2], four: [1, 0] });
		expect(verdictLabel('luckier')).toBe('Luckier than average');
		expect(verdictLabel(null)).toBe('');
	});
});
