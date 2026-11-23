import { describe, expect, it } from 'vitest';
import { boost, buildValue, effectiveLevel, isReached, maxLevel, raisedBy, safeColor, scalingColumns, valueAt } from './kit';
import type { Kit } from './types';

const seg = (text: string) => [[{ text, color: null, italic: false }]];
const KIT: Kit = {
	talents: [
		{ name: 'N', icon: null, role: 'normal', cooldown: null, cost: null, description: seg('n'), scaling: [] },
		{ name: 'S', icon: null, role: 'skill', cooldown: 10, cost: null, description: seg('s'),
			scaling: [{ label: 'DMG', values: Array.from({ length: 15 }, (_, i) => `${i + 1}%`) }] },
		{ name: 'B', icon: null, role: 'burst', cooldown: 15, cost: 60, description: seg('b'), scaling: [] }
	],
	passives: [],
	constellations: [1, 2, 3, 4, 5, 6].map((index) => ({
		index, name: `C${index}`, icon: null, description: seg('c'),
		raises: index === 3 ? ('burst' as const) : index === 5 ? ('skill' as const) : null
	}))
};

describe('kit levels', () => {
	it('finds which constellation raises a talent', () => {
		expect(raisedBy(KIT, 'skill')).toBe(5);
		expect(raisedBy(KIT, 'normal')).toBeNull();
		expect(raisedBy(null, 'skill')).toBeNull();
	});
	it('adds 3 only when that constellation is owned', () => {
		expect(boost(KIT, 'skill', 4)).toBe(0);
		expect(boost(KIT, 'skill', 5)).toBe(3);
		expect(effectiveLevel(9, KIT, 'burst', 3)).toBe(12);
	});
	it('max is 13 when the raising constellation is owned or targeted', () => {
		expect(maxLevel(KIT, 'skill', 2, 2)).toBe(10);
		expect(maxLevel(KIT, 'skill', 2, 6)).toBe(13);
		expect(maxLevel(KIT, 'normal', 6, 6)).toBe(10);
	});
	it('builds now / target / max columns with effective levels', () => {
		expect(scalingColumns(KIT, 'skill', { base: 6, constellation: 2 }, { base: 9, constellation: 6 })).toEqual([
			{ key: 'now', label: 'Lv 6 (now)', level: 6 },
			{ key: 'target', label: 'Lv 12 (target)', level: 12 },
			{ key: 'max', label: 'Lv 13 (max)', level: 13 }
		]);
		expect(scalingColumns(KIT, 'skill', null, null)).toEqual([{ key: 'max', label: 'Lv 10 (max)', level: 10 }]);
	});
	it('a target at or below now is labelled reached and never lower than now', () => {
		expect(scalingColumns(KIT, 'skill', { base: 10, constellation: 0 }, { base: 8, constellation: 0 })).toEqual([
			{ key: 'now', label: 'Lv 10 (now)', level: 10 },
			{ key: 'target', label: 'Lv 10 (reached)', level: 10 },
			{ key: 'max', label: 'Lv 10 (max)', level: 10 }
		]);
		const cols = scalingColumns(KIT, 'skill', { base: 9, constellation: 5 }, { base: 5, constellation: 0 });
		expect(cols[1]).toEqual({ key: 'target', label: 'Lv 12 (reached)', level: 12 });
	});
	it('reads a value at a level, with a dash past the end', () => {
		const row = KIT.talents[1].scaling[0];
		expect(valueAt(row, 1)).toBe('1%');
		expect(valueAt(row, 16)).toBe('—');
	});
});

describe('build values', () => {
	it('a stored null target means same as current', () => {
		expect(buildValue(null, 2)).toBe(2);
		expect(buildValue(undefined, 2)).toBe(2);
		expect(buildValue(6, 2)).toBe(6);
	});
	it('a target at or below current is reached', () => {
		expect(isReached(90, 80)).toBe(true);
		expect(isReached(80, 80)).toBe(true);
		expect(isReached(70, 80)).toBe(false);
	});
});

describe('safeColor', () => {
	it('accepts only #RRGGBB', () => {
		expect(safeColor('#80C0FF')).toBe('#80C0FF');
		expect(safeColor('#80c0ff')).toBe('#80c0ff');
		expect(safeColor('red; background: url(x)')).toBeUndefined();
		expect(safeColor('#80C0FF; x:y')).toBeUndefined();
		expect(safeColor('#fff')).toBeUndefined();
		expect(safeColor(null)).toBeUndefined();
	});
});
