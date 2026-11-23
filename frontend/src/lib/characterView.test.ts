import { afterEach, describe, expect, it, vi } from 'vitest';
import { loadCharacterView, saveCharacterView } from './characterView';

function stubStorage() {
	const store = new Map<string, string>();
	const ls = {
		getItem: (k: string) => store.get(k) ?? null,
		setItem: (k: string, v: string) => void store.set(k, v)
	};
	vi.stubGlobal('localStorage', ls);
	return ls;
}

describe('character view preference', () => {
	afterEach(() => vi.unstubAllGlobals());
	it('defaults', () => {
		stubStorage();
		expect(loadCharacterView()).toEqual({ size: 'small', sort: { az: true, rarity: true, level: false } });
	});
	it('round-trips', () => {
		stubStorage();
		saveCharacterView({ size: 'large', sort: { az: false, rarity: false, level: true } });
		expect(loadCharacterView()).toEqual({ size: 'large', sort: { az: false, rarity: false, level: true } });
	});
	it('ignores corrupt data and blocked storage', () => {
		const ls = stubStorage();
		ls.setItem('aa.characterView', '{"size":"huge","sort":7}');
		expect(loadCharacterView().size).toBe('small');
		vi.stubGlobal('localStorage', { getItem: () => { throw new Error('blocked'); }, setItem: () => { throw new Error('blocked'); } });
		expect(loadCharacterView().size).toBe('small');
		expect(() => saveCharacterView({ size: 'large', sort: { az: true, rarity: true, level: false } })).not.toThrow();
	});
});
