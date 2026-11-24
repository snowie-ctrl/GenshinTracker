// frontend/src/lib/charts.ts
/** Pure SVG geometry for the hand-drawn charts (Wishes, Profile). */
export const ELEMENTS = ['Pyro', 'Hydro', 'Anemo', 'Electro', 'Dendro', 'Cryo', 'Geo'] as const;
export const WEAPON_TYPES = ['Sword', 'Claymore', 'Polearm', 'Bow', 'Catalyst'] as const;

const r1 = (n: number) => Math.round(n * 10) / 10 + 0;   // + 0 turns -0 into 0

export function axisPoint(i: number, n: number, r: number, cx: number, cy: number): { x: number; y: number } {
	const a = -Math.PI / 2 + (2 * Math.PI * i) / n;
	return { x: r1(cx + r * Math.cos(a)), y: r1(cy + r * Math.sin(a)) };
}

export function radarPoints(values: number[], max: number, r: number, cx: number, cy: number): string {
	return values
		.map((v, i) => {
			const p = axisPoint(i, values.length, max > 0 ? (Math.min(v, max) / max) * r : 0, cx, cy);
			return `${p.x},${p.y}`;
		})
		.join(' ');
}

export function dayIndex(date: string): number {
	return Math.round(Date.parse(`${date}T00:00:00Z`) / 86_400_000);
}

export function lineScale(dates: string[], maxY: number, width: number, height: number) {
	const days = dates.map(dayIndex);
	const lo = Math.min(...days);
	const span = Math.max(...days) - lo;
	return {
		x: (date: string) => r1(span === 0 ? width / 2 : ((dayIndex(date) - lo) / span) * width),
		y: (v: number) => r1(height - (maxY > 0 ? (v / maxY) * height : 0))
	};
}

export function linePath(points: { date: string; total: number }[], width: number, height: number): string {
	if (points.length === 0) return '';
	const s = lineScale(points.map((p) => p.date), Math.max(...points.map((p) => p.total)), width, height);
	return points.map((p, i) => `${i ? 'L' : 'M'}${s.x(p.date)},${s.y(p.total)}`).join(' ');
}

export function pityX(pity: number, width: number, maxPity = 90): number {
	return r1((Math.min(pity, maxPity) / maxPity) * width);
}
