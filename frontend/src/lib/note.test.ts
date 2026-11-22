import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { noteTimer } from './note';

describe('noteTimer', () => {
	beforeEach(() => vi.useFakeTimers());
	afterEach(() => vi.useRealTimers());

	it('clears a saved note after a few seconds', () => {
		let note: string | null = null;
		const n = noteTimer((v) => (note = v), 3000);
		n.saved();
		expect(note).toBe('Saved.');
		vi.advanceTimersByTime(2999);
		expect(note).toBe('Saved.');
		vi.advanceTimersByTime(1);
		expect(note).toBeNull();
	});

	it('keeps errors, and an error cancels a pending clear', () => {
		let note: string | null = null;
		const n = noteTimer((v) => (note = v), 3000);
		n.saved();
		n.error('Boom');
		vi.advanceTimersByTime(10_000);
		expect(note).toBe('Boom');
	});

	it('cancel drops a pending clear', () => {
		let note: string | null = null;
		const n = noteTimer((v) => (note = v), 3000);
		n.saved();
		n.cancel();
		vi.advanceTimersByTime(10_000);
		expect(note).toBe('Saved.');
		expect(vi.getTimerCount()).toBe(0);
	});

	it('a second save restarts the timer', () => {
		let note: string | null = null;
		const n = noteTimer((v) => (note = v), 3000);
		n.saved();
		vi.advanceTimersByTime(2000);
		n.saved();
		vi.advanceTimersByTime(2000);
		expect(note).toBe('Saved.');
		vi.advanceTimersByTime(1000);
		expect(note).toBeNull();
	});
});
