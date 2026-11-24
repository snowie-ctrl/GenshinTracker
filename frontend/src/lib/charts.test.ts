// frontend/src/lib/charts.test.ts
import { describe, expect, it } from 'vitest';
import { axisPoint, dayIndex, linePath, pityX, radarPoints } from './charts';

describe('charts', () => {
	it('places radar axes clockwise from the top', () => {
		expect(axisPoint(0, 4, 10, 50, 50)).toEqual({ x: 50, y: 40 });
		expect(axisPoint(1, 4, 10, 50, 50)).toEqual({ x: 60, y: 50 });
		expect(axisPoint(2, 4, 10, 50, 50)).toEqual({ x: 50, y: 60 });
	});
	it('scales radar values to the max and clamps', () => {
		expect(radarPoints([1, 0, 1, 0], 1, 10, 50, 50)).toBe('50,40 50,50 50,60 50,50');
		expect(radarPoints([5, 0, 0, 0], 2, 10, 50, 50)).toBe('50,40 50,50 50,50 50,50');
		expect(radarPoints([0, 0, 0], 0, 10, 50, 50)).toBe('50,50 50,50 50,50');
	});
	it('builds a line path on a day scale', () => {
		expect(dayIndex('1970-01-02')).toBe(1);
		expect(linePath([{ date: '2026-01-01', total: 160 }, { date: '2026-01-03', total: 320 }], 100, 50))
			.toBe('M0,25 L100,0');
		expect(linePath([{ date: '2026-01-01', total: 160 }], 100, 50)).toBe('M50,0');
		expect(linePath([], 100, 50)).toBe('');
	});
	it('maps pity to an x position', () => {
		expect(pityX(45, 180)).toBe(90);
		expect(pityX(120, 180)).toBe(180);
	});
});
