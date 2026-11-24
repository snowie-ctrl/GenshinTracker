import { describe, expect, it } from 'vitest';
import { buildAxis, DAY, dayStart, dayTicks, placeBars, todayOffset } from './timeline';

const now = new Date(2026, 10, 23, 12, 0, 0).getTime();
const iso = (days: number) => new Date(now + days * DAY).toISOString();

describe('buildAxis', () => {
	it('runs from 21 days back to at least 14 days ahead', () => {
		const a = buildAxis([], now);
		expect(a.start).toBe(dayStart(now) - 21 * DAY);
		expect(a.days).toBe(21 + 14 + 1);
	});
	it('extends to the latest end but clamps far ends to 60 days', () => {
		expect(buildAxis([{ start: iso(-1), end: iso(30) }], now).days).toBe(21 + 30 + 1);
		expect(buildAxis([{ start: iso(-1), end: iso(300) }], now).days).toBe(21 + 60 + 1);
	});
});

describe('placeBars', () => {
	const axis = buildAxis([], now);
	it('packs non-overlapping bars into one lane and overlapping ones into new lanes', () => {
		const rows = [
			{ id: 'a', start: iso(-10), end: iso(-5) },
			{ id: 'b', start: iso(-4), end: iso(2) },
			{ id: 'c', start: iso(-3), end: iso(1) }
		];
		const placed = placeBars(rows, axis);
		expect(placed.map((p) => [p.row.id, p.lane])).toEqual([['a', 0], ['b', 0], ['c', 1]]);
	});
	it('clamps far ends and marks them', () => {
		const [p] = placeBars([{ start: iso(-1), end: iso(300) }], axis);
		expect(p.clampedEnd).toBe(true);
		expect(p.left + p.width).toBeCloseTo(1, 5);
	});
	it('missing start uses axis start', () => {
		const [p] = placeBars([{ start: null, end: iso(3) }], axis);
		expect(p.left).toBe(0);
		expect(p.width).toBeGreaterThan(0);
	});
	it('drops rows without an end and rows wholly before the axis', () => {
		expect(placeBars([{ start: iso(-1), end: null }, { start: iso(-60), end: iso(-30) }], axis)).toEqual([]);
	});
});

describe('todayOffset and ticks', () => {
	it('puts today 21.5 days into a 36-day axis', () => {
		const a = buildAxis([], now);
		expect(todayOffset(a, now)).toBeCloseTo(21.5 / 36, 5);
	});
	it('labels month starts with the month name', () => {
		const ticks = dayTicks(buildAxis([], now));
		expect(ticks).toHaveLength(36);
		const dec = ticks.find((t) => t.monthStart);
		expect(dec?.label).toBe('Dec');
	});
});
