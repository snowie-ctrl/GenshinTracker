import { describe, expect, it } from 'vitest';
import {
	bannerPity, buildTileView, covered, dayButtons, expeditionsReady, greeting, moveItem, topReward
} from './dashboard';
import type { BuildMaterial } from './types';

const m = (need: number, have: number, craft: number): BuildMaterial => ({
	id: 1, name: 'Guide', icon: 'x', rarity: 3, category: 'talent', category_label: 'Talent books', need, have, craft
});

describe('greeting', () => {
	it('picks the part of the day and falls back to Traveler', () => {
		expect(greeting(4, '')).toBe('Good evening, Traveler');
		expect(greeting(5, 'Lumine')).toBe('Good morning, Lumine');
		expect(greeting(12, '  ')).toBe('Good afternoon, Traveler');
		expect(greeting(18, 'Aether')).toBe('Good evening, Aether');
	});
});

describe('dayButtons', () => {
	it('marks viewed and today separately', () => {
		const b = dayButtons(2, 4);
		expect(b.map((x) => x.label)).toEqual(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']);
		expect(b.filter((x) => x.viewed).map((x) => x.day)).toEqual([2]);
		expect(b.filter((x) => x.today).map((x) => x.day)).toEqual([4]);
	});
});

describe('moveItem', () => {
	it('moves and ignores out-of-range moves', () => {
		expect(moveItem(['a', 'b', 'c'], 2, 0)).toEqual(['c', 'a', 'b']);
		expect(moveItem(['a', 'b', 'c'], 0, 1)).toEqual(['b', 'a', 'c']);
		expect(moveItem(['a', 'b'], 0, -1)).toEqual(['a', 'b']);
		expect(moveItem(['a', 'b'], 1, 2)).toEqual(['a', 'b']);
	});
});

describe('buildTileView', () => {
	it('shows allocation, craft hint and what is still missing', () => {
		expect(buildTileView(m(9, 8, 1))).toEqual({ main: '8/9', badge: null, hint: '+1 craft', tone: 'met' });
		expect(buildTileView(m(9, 2, 3))).toEqual({ main: '2/9', badge: '−4', hint: '+3 craft', tone: 'short' });
		expect(buildTileView(m(20, 0, 0))).toEqual({ main: '0/20', badge: '−20', hint: null, tone: 'short' });
		expect(covered(m(9, 8, 1))).toBe(true);
		expect(covered(m(9, 8, 0))).toBe(false);
	});
});

describe('misc', () => {
	it('topReward prefers rarity, then count', () => {
		const r = (id: number, rarity: number, count: number) => ({ id, name: `R${id}`, icon: '', rarity, count });
		expect(topReward([])).toBeNull();
		expect(topReward([r(1, 4, 100), r(2, 5, 60), r(3, 5, 420)])?.id).toBe(3);
	});
	it('expeditionsReady counts finished or returned', () => {
		const now = Date.parse('2026-11-22T12:00:00Z');
		expect(expeditionsReady([
			{ icon: '', finished: true, return_at: '2026-11-22T15:00:00Z' },
			{ icon: '', finished: false, return_at: '2026-11-22T11:00:00Z' },
			{ icon: '', finished: false, return_at: '2026-11-22T13:00:00Z' }
		], now)).toBe(2);
	});
	it('bannerPity', () => {
		expect(bannerPity(null)).toBeNull();
		expect(bannerPity({ pool: 'character', pity5: 2, hard: 90, next_state: '50/50', fate_points: null }))
			.toBe('Pity 2/90 · 50/50');
		expect(bannerPity({ pool: 'weapon', pity5: 62, hard: 80, next_state: 'guaranteed', fate_points: 1 }))
			.toBe('Pity 62/80 · guaranteed');
	});
});
