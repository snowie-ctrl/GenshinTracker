import { describe, expect, it } from 'vitest';
import { emptyTarget, moveSub, setSlot, setsFor, SLOT_OPTIONS, sourceLabel, STAT_LABELS, SUB_KEYS, toggleStat } from './artifacts';

describe('artifacts helpers', () => {
	it('labels every option and substat', () => {
		for (const k of [...SLOT_OPTIONS.sands, ...SLOT_OPTIONS.goblet, ...SLOT_OPTIONS.circlet, ...SUB_KEYS]) {
			expect(STAT_LABELS[k]).toBeTruthy();
		}
		expect(STAT_LABELS['crit_dmg']).toBe('CRIT DMG');
		expect(SLOT_OPTIONS.goblet).toContain('pyro');
		expect(SLOT_OPTIONS.sands).not.toContain('crit_rate');
	});
	it('empty target', () => {
		expect(emptyTarget()).toEqual({ sets: [], main: { sands: [], goblet: [], circlet: [] }, subs: [] });
	});
	it('toggles a stat', () => {
		expect(toggleStat(['er'], 'atk%')).toEqual(['er', 'atk%']);
		expect(toggleStat(['er', 'atk%'], 'er')).toEqual(['atk%']);
	});
	it('moves a substat', () => {
		expect(moveSub(['a', 'b', 'c'], 2, 0)).toEqual(['c', 'a', 'b']);
		expect(moveSub(['a', 'b'], 0, 5)).toEqual(['a', 'b']);
	});
	it('switching mode keeps the first set', () => {
		expect(setsFor(2, [{ set_id: 1, pieces: 4 }])).toEqual([{ set_id: 1, pieces: 2 }]);
		expect(setsFor(4, [{ set_id: 1, pieces: 2 }, { set_id: 2, pieces: 2 }])).toEqual([{ set_id: 1, pieces: 4 }]);
		expect(setsFor(4, [])).toEqual([]);
	});
	it('sets a picker slot', () => {
		expect(setSlot([], 0, 5, 4)).toEqual([{ set_id: 5, pieces: 4 }]);
		expect(setSlot([{ set_id: 5, pieces: 2 }], 1, 6, 2)).toEqual([{ set_id: 5, pieces: 2 }, { set_id: 6, pieces: 2 }]);
		expect(setSlot([{ set_id: 5, pieces: 2 }, { set_id: 6, pieces: 2 }], 0, null, 2)).toEqual([{ set_id: 6, pieces: 2 }]);
		expect(setSlot([{ set_id: 5, pieces: 2 }], 1, 5, 2)).toEqual([{ set_id: 5, pieces: 2 }]);   // same set twice: ignored
	});
	it('source label', () => {
		expect(sourceLabel({ id: 1, name: 'N', icon: 'x', domain: { id: 2, name: 'D', entrance: 'Clear Pool', region: 'Liyue' } })).toBe('Clear Pool');
		expect(sourceLabel({ id: 1, name: 'G', icon: 'x', domain: null })).toBe('Not from a domain');
		expect(sourceLabel(undefined)).toBe('Drop source unknown');
	});
});
