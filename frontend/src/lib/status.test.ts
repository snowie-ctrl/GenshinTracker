import { describe, expect, it } from 'vitest';
import type { Character } from './types';
import { DEFAULT_SORT, deriveStatus, emptyFilters, groupCharacters, progressTooltip, sortCharacters, statusLine } from './status';

function char(over: Partial<Character>): Character {
	return {
		id: 1, slug: 'x', name: 'X', rarity: 4, element: 'Pyro', weapon_type: 'Sword',
		icon: 'UI_AvatarIcon_X', splash: null, owned: true, level: 80, constellation: 2,
		friendship: 10, talents: { normal: 6, skill: 8, burst: 8 }, weapon: null, goal: 'none',
		targets: null, status: 'obtained', prefarming: false, progress: null, planned_weapon_id: null, artifact_target: null, artifacts_done: false, priority: null, team_tags: [], release_at: null, ...over
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

	it('sorts every section with the same keys (default: rarity then name)', () => {
		const g = groupCharacters(list, emptyFilters());
		for (const section of Object.values(g)) {
			expect(section).toEqual(sortCharacters(section, DEFAULT_SORT));
		}
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

	it('team tag filter keeps characters in a team with every selected tag', () => {
		const f = { ...emptyFilters(), teamTags: [2] };
		const a = char({ id: 1, slug: 'a', team_tags: [[1, 2]] });
		const b = char({ id: 2, slug: 'b', team_tags: [[1]] });
		expect(groupCharacters([a, b], f).obtained.map((c) => c.slug)).toEqual(['a']);
	});
});

describe('sortCharacters', () => {
	const c = (name: string, rarity: number, level: number | null, release_at: string | null, owned = level !== null) =>
		({ name, rarity, level, release_at, owned }) as unknown as Character;
	const list = [c('Bennett', 4, 90, '2020-09-28'), c('Albedo', 5, 20, '2020-12-23'), c('Nahida', 5, 90, '2022-11-02'),
		c('Yelan', 5, null, '2022-05-31'), c('Mystery', 4, null, null)];
	const names = (k: { az: boolean; rarity: boolean; level: boolean }) => sortCharacters(list, k).map((x) => x.name);
	it('A-Z only', () => expect(names({ az: true, rarity: false, level: false })).toEqual(['Albedo', 'Bennett', 'Mystery', 'Nahida', 'Yelan']));
	it('rarity then A-Z', () => expect(names({ az: true, rarity: true, level: false })).toEqual(['Albedo', 'Nahida', 'Yelan', 'Bennett', 'Mystery']));
	it('rarity, level, A-Z; unowned count as 0', () =>
		expect(names({ az: true, rarity: true, level: true })).toEqual(['Nahida', 'Albedo', 'Yelan', 'Bennett', 'Mystery']));
	it('A-Z off: newest first, unknown release last', () =>
		expect(names({ az: false, rarity: false, level: false })).toEqual(['Nahida', 'Yelan', 'Albedo', 'Bennett', 'Mystery']));
	it('does not mutate its input', () => {
		const before = list.map((x) => x.name);
		sortCharacters(list, { az: true, rarity: true, level: true });
		expect(list.map((x) => x.name)).toEqual(before);
	});
});
