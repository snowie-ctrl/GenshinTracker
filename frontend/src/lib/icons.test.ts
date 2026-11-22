import { describe, expect, it } from 'vitest';
import { ICON_NAMES, ICONS } from './icons';

describe('icons', () => {
	it('has at least one path, starting with a move, for every name', () => {
		expect(ICON_NAMES).toHaveLength(11);
		for (const name of ICON_NAMES) {
			expect(ICONS[name].length).toBeGreaterThan(0);
			for (const p of ICONS[name]) expect(p.d).toMatch(/^M/);
		}
	});
});
