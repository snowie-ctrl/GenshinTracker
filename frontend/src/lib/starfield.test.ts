import { describe, expect, it } from 'vitest';
import { LAYERS, TILE, backgroundAnimated, layerColors, makeStars, nebula, starTile } from './starfield';

describe('makeStars', () => {
	it('is deterministic for a seed and differs between seeds', () => {
		expect(makeStars(7, 50, 0.4, 1)).toEqual(makeStars(7, 50, 0.4, 1));
		expect(makeStars(7, 50, 0.4, 1)).not.toEqual(makeStars(8, 50, 0.4, 1));
	});
	it('keeps every star inside the tile, away from the edge, within the radius range', () => {
		const stars = makeStars(3, 400, 0.5, 1.5);
		expect(stars).toHaveLength(400);
		for (const s of stars) {
			expect(s.x).toBeGreaterThanOrEqual(2);
			expect(s.x).toBeLessThanOrEqual(TILE.w - 2);
			expect(s.y).toBeGreaterThanOrEqual(2);
			expect(s.y).toBeLessThanOrEqual(TILE.h - 2);
			expect(s.r).toBeGreaterThanOrEqual(0.5);
			expect(s.r).toBeLessThanOrEqual(1.5);
			expect(s.o).toBeGreaterThan(0);
			expect(s.o).toBeLessThanOrEqual(1);
		}
	});
});

describe('starTile', () => {
	it('returns an encoded SVG data URL sized to the tile with one circle per star', () => {
		const css = starTile(makeStars(1, 3, 1, 1), '#ffeccc');
		expect(css.startsWith('url("data:image/svg+xml,')).toBe(true);
		const svg = decodeURIComponent(css.slice('url("data:image/svg+xml,'.length, -2));
		expect(svg).toContain(`width="${TILE.w}"`);
		expect(svg).toContain(`height="${TILE.h}"`);
		expect(svg.match(/<circle/g)).toHaveLength(3);
		expect(svg).toContain('#ffeccc');
	});
});

describe('backgroundAnimated', () => {
	it('animates only when the setting is on and reduced motion is off', () => {
		expect(backgroundAnimated(true, false)).toBe(true);
		expect(backgroundAnimated(true, true)).toBe(false);
		expect(backgroundAnimated(false, false)).toBe(false);
		expect(backgroundAnimated(false, true)).toBe(false);
	});
});

describe('LAYERS', () => {
	it('has three layers, nearer ones faster', () => {
		expect(LAYERS.map((l) => l.seconds)).toEqual([90, 55, 35]);
	});
});

describe('tint', () => {
	it('keeps the fine layer white and tints the two nearer layers', () => {
		expect(layerColors(null)).toEqual(LAYERS.map((l) => l.color));
		expect(layerColors('#4cc2f1')).toEqual(['#ffffff', '#4cc2f1', '#4cc2f1']);
	});
	it('tints the nebula', () => {
		expect(nebula(null)).toContain('rgba(59, 47, 107');
		expect(nebula('#ef7a4a')).toContain('#ef7a4a');
	});
});
