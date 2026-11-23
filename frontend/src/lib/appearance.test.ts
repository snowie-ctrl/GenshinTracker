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
	it('a load that lands after the user toggled does not overwrite the choice', async () => {
		let finish!: (v: { background_animated: boolean }) => void;
		const slow = new Promise<{ background_animated: boolean }>((r) => (finish = r));
		const a = createAppearance(() => slow, vi.fn().mockResolvedValue({}));
		const loading = a.load();
		await a.setBackgroundAnimated(false);
		finish({ background_animated: true });      // the server value read before the toggle was saved
		await loading;
		expect(a.backgroundAnimated).toBe(false);
	});
	it('a load that lands while the toggle is still saving does not overwrite it', async () => {
		let finishLoad!: (v: { background_animated: boolean }) => void;
		let finishSave!: () => void;
		const a = createAppearance(
			() => new Promise((r) => (finishLoad = r)),
			() => new Promise<void>((r) => (finishSave = r))
		);
		const loading = a.load();
		const saving = a.setBackgroundAnimated(false);
		finishLoad({ background_animated: true });
		await loading;
		expect(a.backgroundAnimated).toBe(false);
		finishSave();
		await saving;
		expect(a.backgroundAnimated).toBe(false);
	});
	it('a failed toggle falls back to a value loaded while it was saving', async () => {
		let finishLoad!: (v: { background_animated: boolean }) => void;
		let failSave!: (e: Error) => void;
		const a = createAppearance(
			() => new Promise((r) => (finishLoad = r)),
			() => new Promise<void>((_, rej) => (failSave = rej))
		);
		const loading = a.load();
		const saving = a.setBackgroundAnimated(true);
		finishLoad({ background_animated: false });
		await loading;
		failSave(new Error('Save failed'));
		await expect(saving).rejects.toThrow('Save failed');
		expect(a.backgroundAnimated).toBe(false);
	});
	it('a load that lands after a failed toggle still applies the saved value', async () => {
		let finish!: (v: { background_animated: boolean }) => void;
		const slow = new Promise<{ background_animated: boolean }>((r) => (finish = r));
		const a = createAppearance(() => slow, () => Promise.reject(new Error('Save failed')));
		const loading = a.load();
		await expect(a.setBackgroundAnimated(true)).rejects.toThrow('Save failed');
		finish({ background_animated: false });
		await loading;
		expect(a.backgroundAnimated).toBe(false);
	});
	it('keeps the new value when saving works', async () => {
		const save = vi.fn().mockResolvedValue({});
		const a = createAppearance(async () => ({ background_animated: true }), save);
		await a.setBackgroundAnimated(false);
		expect(save).toHaveBeenCalledWith(false);
		expect(a.backgroundAnimated).toBe(false);
	});
});
