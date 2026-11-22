import { describe, expect, it } from 'vitest';
import { skippedNote } from './syncLabel';

describe('skippedNote', () => {
	it('names the hourly throttle skip', () => {
		expect(skippedNote({ ok: true, skipped: 'fresh' })).toBe('skipped: fresh');
	});
	it('lists skipped characters by name', () => {
		expect(skippedNote({ ok: true, count: 3, skipped: ['Traveler'] })).toBe('skipped: Traveler');
		expect(skippedNote({ ok: true, skipped: ['Traveler', 'Aloy'] })).toBe('skipped: Traveler, Aloy');
	});
	it('says nothing when nothing was skipped', () => {
		expect(skippedNote({ ok: true })).toBe('');
		expect(skippedNote({ ok: true, skipped: [] })).toBe('');	});
});
