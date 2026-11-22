import { describe, expect, it } from 'vitest';
import { initialTab } from './maps';

describe('initialTab', () => {
	it('uses the stored tab when valid, otherwise the default', () => {
		expect(initialTab('appsample', 'hoyolab')).toBe('appsample');
		expect(initialTab(null, 'appsample')).toBe('appsample');
		expect(initialTab('google', 'hoyolab')).toBe('hoyolab');
	});
});
