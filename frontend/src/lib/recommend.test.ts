import { describe, expect, it } from 'vitest';
import { applyRecommendation, matchesRecommendation } from './recommend';
import type { ArtifactTarget, StatRecommendation } from './types';

const rec: StatRecommendation = {
	main: { sands: ['er', 'hp%'], goblet: ['pyro'], circlet: ['crit_rate', 'crit_dmg'] },
	subs: ['er', 'crit_rate'], synced_at: '2026-11-24T00:00:00Z'
};
const target: ArtifactTarget = {
	sets: [{ set_id: 15007, pieces: 4 }],
	main: { sands: ['atk%'], goblet: [], circlet: [] }, subs: ['em']
};

describe('applyRecommendation', () => {
	it('replaces main and subs and keeps sets', () => {
		expect(applyRecommendation(target, rec)).toEqual({
			sets: [{ set_id: 15007, pieces: 4 }],
			main: { sands: ['er', 'hp%'], goblet: ['pyro'], circlet: ['crit_rate', 'crit_dmg'] },
			subs: ['er', 'crit_rate']
		});
	});
	it('builds a full target when there is none', () => {
		expect(applyRecommendation(null, rec).sets).toEqual([]);
		expect(applyRecommendation(null, rec).subs).toEqual(['er', 'crit_rate']);
	});
	it('does not share arrays with the recommendation', () => {
		const out = applyRecommendation(null, rec);
		out.main.sands.push('em');
		expect(rec.main.sands).toEqual(['er', 'hp%']);
	});
});

describe('matchesRecommendation', () => {
	it('is true after applying', () => {
		expect(matchesRecommendation(applyRecommendation(target, rec), rec)).toBe(true);
	});
	it('ignores order within a main slot', () => {
		const t = applyRecommendation(null, rec);
		t.main.sands = ['hp%', 'er'];
		expect(matchesRecommendation(t, rec)).toBe(true);
	});
	it('is order-sensitive for substats', () => {
		const t = applyRecommendation(null, rec);
		t.subs = ['crit_rate', 'er'];
		expect(matchesRecommendation(t, rec)).toBe(false);
	});
	it('is false for a different target or none', () => {
		expect(matchesRecommendation(target, rec)).toBe(false);
		expect(matchesRecommendation(null, rec)).toBe(false);
	});
});
