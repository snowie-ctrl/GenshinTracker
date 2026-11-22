import { describe, expect, it } from 'vitest';
import type { EventRow } from './types';
import { leftTotals, primosLine, sortEvents, timeLeft } from './events';

const NOW = Date.parse('2026-11-21T12:00:00Z');

function row(id: number, end: string | null, done = false, primogems = 0): EventRow {
	return { id, name: `E${id}`, description: '', start: null, end, rewards: [], primogems, done, ending_soon: false };
}

describe('timeLeft', () => {
	it('formats days, hours, minutes', () => {
		expect(timeLeft('2026-11-23T15:30:00Z', NOW)).toBe('2d 3h');
		expect(timeLeft('2026-11-21T15:30:00Z', NOW)).toBe('3h 30m');
		expect(timeLeft('2026-11-21T12:05:00Z', NOW)).toBe('5m');
		expect(timeLeft('2026-11-21T11:00:00Z', NOW)).toBe('ended');
		expect(timeLeft(null, NOW)).toBe('—');
	});
});

describe('events', () => {
	it('sorts not-done by end, done last', () => {
		const rows = [row(1, '2026-11-30T00:00:00Z'), row(2, '2026-11-22T00:00:00Z', true), row(3, '2026-11-25T00:00:00Z'), row(4, null)];
		expect(sortEvents(rows).map((r) => r.id)).toEqual([3, 1, 4, 2]);
	});
	it('totals and line', () => {
		const t = leftTotals([row(1, null, false, 420), row(2, null, true, 60), row(3, null, false, 0)]);
		expect(t).toEqual({ count: 2, primogems: 420 });
		expect(primosLine(t)).toBe('2 left · 420 primos unclaimed');
		expect(primosLine({ count: 0, primogems: 0 })).toBe('All events done ✓');
	});
});
