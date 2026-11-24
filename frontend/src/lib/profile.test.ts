import { describe, expect, it } from 'vitest';
import { moveId, ringDash, talentLine, tileTitle, toggleId, topBosses } from './profile';

describe('profile helpers', () => {
	it('toggles ids with a cap', () => {
		expect(toggleId([1, 2], 2)).toEqual([1]);
		expect(toggleId([1], 2)).toEqual([1, 2]);
		expect(toggleId([1, 2, 3, 4, 5, 6, 7, 8], 9)).toEqual([1, 2, 3, 4, 5, 6, 7, 8]);
	});
	it('moves ids up and down within bounds', () => {
		expect(moveId([1, 2, 3], 1, -1)).toEqual([2, 1, 3]);
		expect(moveId([1, 2, 3], 2, 1)).toEqual([1, 2, 3]);
		expect(moveId([1, 2, 3], 0, -1)).toEqual([1, 2, 3]);
	});
	it('draws a ring dash for a percentage', () => {
		expect(ringDash(50)).toBe('47.1 94.2');
		expect(ringDash(150)).toBe('94.2 94.2');
		expect(ringDash(-5)).toBe('0.0 94.2');
	});
	it('formats tiles, talents and bosses', () => {
		expect(tileTitle({ key: 'chest', label: 'Chests', value: 3, detail: [{ label: 'Common', value: 2 }, { label: 'Rare', value: 1 }] }))
			.toBe('Common 2 · Rare 1');
		expect(tileTitle({ key: 'domain', label: 'Domains', value: 3 })).toBe('');
		expect(talentLine({ normal: 6, skill: 10, burst: null })).toBe('6 / 10 / —');
		const bosses = Array.from({ length: 8 }, (_, i) => ({ name: `B${i}`, kills: 8 - i }));
		expect(topBosses(bosses, false)).toHaveLength(6);
		expect(topBosses(bosses, true)).toHaveLength(8);
	});
});
