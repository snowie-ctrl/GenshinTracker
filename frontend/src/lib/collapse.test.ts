import { afterEach, describe, expect, it, vi } from 'vitest';
import { loadCollapsed, saveCollapsed } from './collapse';

describe('collapse state', () => {
	afterEach(() => vi.unstubAllGlobals());

	it('defaults to unobtained collapsed when storage is unavailable', () => {
		vi.stubGlobal('localStorage', {
			getItem: () => { throw new Error('blocked'); },
			setItem: () => { throw new Error('blocked'); }
		});
		expect(loadCollapsed()).toEqual({ building: false, obtained: false, wanted: false, unobtained: true });
		expect(() => saveCollapsed({ building: true, obtained: false, wanted: false, unobtained: true })).not.toThrow();
	});

	it('round-trips through storage', () => {
		const store = new Map<string, string>();
		vi.stubGlobal('localStorage', {
			getItem: (k: string) => store.get(k) ?? null,
			setItem: (k: string, v: string) => store.set(k, v)
		});
		saveCollapsed({ building: true, obtained: false, wanted: false, unobtained: false });
		expect(loadCollapsed().building).toBe(true);
		expect(loadCollapsed().unobtained).toBe(false);
	});
});
