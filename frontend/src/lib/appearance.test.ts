import { describe, expect, it, vi } from 'vitest';
import { createAppearance } from './appearance.svelte';

describe('appearance store', () => {
	it('defaults to animated and keeps it when loading fails', async () => {
		const a = createAppearance(() => Promise.reject(new Error('down')), vi.fn());
		await a.load();
		expect(a.backgroundAnimated).toBe(true);
	});
	it('takes the saved value on load', async () => {
		const a = createAppearance(async () => ({ background_animated: false }), vi.fn());
		await a.load();
		expect(a.backgroundAnimated).toBe(false);
	});
	it('reverts and rethrows when saving fails', async () => {
		const a = createAppearance(async () => ({ background_animated: true }), () => Promise.reject(new Error('Save failed')));
		await a.load();
		await expect(a.setBackgroundAnimated(false)).rejects.toThrow('Save failed');
		expect(a.backgroundAnimated).toBe(true);
	});
	it('keeps the new value when saving works', async () => {
		const save = vi.fn().mockResolvedValue({});
		const a = createAppearance(async () => ({ background_animated: true }), save);
		await a.setBackgroundAnimated(false);
		expect(save).toHaveBeenCalledWith(false);
		expect(a.backgroundAnimated).toBe(false);
	});
});
