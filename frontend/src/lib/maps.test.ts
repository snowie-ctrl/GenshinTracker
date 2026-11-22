import { describe, expect, it } from 'vitest';
import { initialTab, nextTab } from './maps';

describe('initialTab', () => {
	it('uses the stored tab when valid, otherwise the default', () => {
		expect(initialTab('appsample', 'hoyolab')).toBe('appsample');
		expect(initialTab(null, 'appsample')).toBe('appsample');
		expect(initialTab('google', 'hoyolab')).toBe('hoyolab');
	});
});

describe('nextTab', () => {
	const keys = ['a', 'b', 'c'];
	it('moves with ArrowLeft/ArrowRight and wraps', () => {
		expect(nextTab(keys, 'a', 'ArrowRight')).toBe('b');
		expect(nextTab(keys, 'c', 'ArrowRight')).toBe('a');
		expect(nextTab(keys, 'a', 'ArrowLeft')).toBe('c');
	});
	it('jumps with Home/End and ignores other keys', () => {
		expect(nextTab(keys, 'b', 'Home')).toBe('a');
		expect(nextTab(keys, 'b', 'End')).toBe('c');
		expect(nextTab(keys, 'b', 'Enter')).toBeNull();
	});
});
