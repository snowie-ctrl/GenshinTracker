import { describe, expect, it } from 'vitest';
import type { Character } from './types';
import { deriveStatus, emptyFilters, groupCharacters, progressTooltip, statusLine } from './status';

function char(over: Partial<Character>): Character {
	return {
		id: 1, slug: 'x', name: 'X', rarity: 4, element: 'Pyro', weapon_type: 'Sword',
		icon: 'UI_AvatarIcon_X', splash: null, owned: true, level: 80, constellation: 2,
		friendship: 10, talents: { normal: 6, skill: 8, burst: 8 }, weapon: null, goal: 'none',
		targets: null, status: 'obtained', prefarming: false, progress: null, ...over
	};
}

describe('deriveStatus', () => {
	it('matches backend rules', () => {
		expect(deriveStatus(false, 'none')).toEqual({ status: 'unobtained', prefarming: false });
		expect(deriveStatus(false, 'want')).toEqual({ status: 'wanted', prefarming: false });
		expect(deriveStatus(false, 'build')).toEqual({ status: 'wanted', prefarming: true });
		expect(deriveStatus(true, 'want')).toEqual({ status: 'obtained', prefarming: false });
		expect(deriveStatus(true, 'build')).toEqual({ status: 'building', prefarming: false });
	});
});

describe('statusLine', () => {
	it('shows level and constellation for obtained', () => {
		expect(statusLine(char({}))).toBe('Lv 80 · C2');
	});
	it('shows wanted / pre-farming', () => {
		expect(statusLine(char({ status: 'wanted', owned: false }))).toBe('Wanted');
		expect(statusLine(char({ status: 'wanted', owned: false, prefarming: true }))).toBe('Pre-farming');
	});
	it('is empty for unobtained', () => {
		expect(statusLine(char({ status: 'unobtained', owned: false }))).toBe('');
	});
});

describe('progressTooltip', () => {
	it('shows current → target', () => {
		const c = char({ status: 'building', targets: { level: 90, normal: 8, skill: 8, burst: 8, weapon_level: 90 } });
		expect(progressTooltip(c)).toBe('Lv 80→90 · 6/8/8 → 8/8/8');
	});
});

describe('groupCharacters', () => {
	const list = [
		char({ id: 1, name: 'Bennett', status: 'building', progress: 0.9 }),
		char({ id: 2, name: 'Furina', status: 'building', progress: 0.4, rarity: 5, element: 'Hydro' }),
		char({ id: 3, name: 'Xiangling', status: 'obtained' }),
		char({ id: 4, name: 'Nahida', status: 'obtained', rarity: 5, element: 'Dendro', weapon_type: 'Catalyst' }),
		char({ id: 5, name: 'Kazuha', status: 'wanted', owned: false, rarity: 5, element: 'Anemo' })
	];

	it('sorts building by progress ascending, others by rarity then element order', () => {
		const g = groupCharacters(list, emptyFilters());
		expect(g.building.map((c) => c.name)).toEqual(['Furina', 'Bennett']);
		expect(g.obtained.map((c) => c.name)).toEqual(['Nahida', 'Xiangling']);
		expect(g.wanted.map((c) => c.name)).toEqual(['Kazuha']);
		expect(g.unobtained).toEqual([]);
	});

	it('applies filters inside every section', () => {
		const g = groupCharacters(list, { ...emptyFilters(), elements: ['Pyro'] });
		expect(g.building.map((c) => c.name)).toEqual(['Bennett']);
		expect(g.obtained.map((c) => c.name)).toEqual(['Xiangling']);
		const s = groupCharacters(list, { ...emptyFilters(), search: 'nah' });
		expect(s.obtained.map((c) => c.name)).toEqual(['Nahida']);
		const w = groupCharacters(list, { ...emptyFilters(), weapons: ['Catalyst'], rarities: [5] });
		expect(w.obtained.map((c) => c.name)).toEqual(['Nahida']);
	});
});
