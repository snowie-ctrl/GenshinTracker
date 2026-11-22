import { describe, expect, it } from 'vitest';
import type { EventRow } from './types';
import { countdownWarn, eventsLeft, leftTotals, primosLine, setDone, sortEvents, timeLeft } from './events';

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
		expect(primosLine(t)).toBe('2 events left · 420 primos unclaimed');
		expect(primosLine({ count: 1, primogems: 60 })).toBe('1 event left · 60 primos unclaimed');
		expect(primosLine({ count: 0, primogems: 0 })).toBe('All events done ✓');
	});
	it('setDone changes only that row and keeps other rows as they are', () => {
		const rows = [row(1, '2026-11-30T00:00:00Z', true), row(2, '2026-11-22T00:00:00Z'), row(3, '2026-11-25T00:00:00Z', true)];
		const got = setDone(rows, 2, true);
		expect(got.map((r) => [r.id, r.done])).toEqual([[2, true], [3, true], [1, true]]);
		// reverting row 3 later leaves row 2's newer state alone, and re-sorts
		expect(setDone(got, 3, false).map((r) => [r.id, r.done])).toEqual([[3, false], [2, true], [1, true]]);
	});
	it('pluralises events left', () => {
		expect(eventsLeft(1)).toBe('1 event left');
		expect(eventsLeft(3)).toBe('3 events left');
	});
});

describe('countdownWarn', () => {
	it('warns only when asked and the time is under 24 h away', () => {
		expect(countdownWarn('2026-11-21T15:00:00Z', NOW, true)).toBe(true);
		expect(countdownWarn('2026-11-21T15:00:00Z', NOW, false)).toBe(false);
		expect(countdownWarn('2026-11-23T15:00:00Z', NOW, true)).toBe(false);
	});
	it('never warns for past or missing times', () => {
		expect(countdownWarn('2026-11-21T11:00:00Z', NOW, true)).toBe(false);
		expect(countdownWarn(null, NOW, true)).toBe(false);
	});
});
