import { describe, expect, it } from 'vitest';
import { clampCons, clampTalent, editable, unlockLocked } from './traveler';
import type { TravelerInfo } from './types';

const t = (p: Partial<TravelerInfo>): TravelerInfo => ({
	element_id: 1000000502, current: false, seen: false, unlocked: false,
	talents: { normal: 1, skill: 1, burst: 1 }, constellation: 0, source: 'manual', ...p
});

describe('traveler helpers', () => {
	it('clamps talents and constellation', () => {
		expect([clampTalent(0), clampTalent(11), clampTalent(NaN), clampTalent(7.6)]).toEqual([1, 10, 1, 7]);
		expect([clampCons(-1), clampCons(9), clampCons(NaN), clampCons(3)]).toEqual([0, 6, 0, 3]);
	});
	it('locks the current element and seen unlocks', () => {
		expect(editable(t({ current: true }))).toBe(false);
		expect(editable(t({}))).toBe(true);
		expect(unlockLocked(t({ seen: true }))).toBe(true);
		expect(unlockLocked(t({}))).toBe(false);
	});
});
