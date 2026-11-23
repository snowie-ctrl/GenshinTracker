/** Seeded star tiles for the drifting-dust background. Pure: no DOM. */
export const TILE = { w: 1400, h: 900 } as const;

export interface Star { x: number; y: number; r: number; o: number }

/** mulberry32: small, fast, deterministic PRNG returning [0, 1). */
function rng(seed: number): () => number {
	let a = seed >>> 0;
	return () => {
		a = (a + 0x6d2b79f5) >>> 0;
		let t = a;
		t = Math.imul(t ^ (t >>> 15), t | 1);
		t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
		return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
	};
}

const round = (n: number) => Math.round(n * 100) / 100;

export function makeStars(seed: number, count: number, rMin: number, rMax: number): Star[] {
	const next = rng(seed);
	return Array.from({ length: count }, () => ({
		x: round(2 + next() * (TILE.w - 4)),
		y: round(2 + next() * (TILE.h - 4)),
		r: round(rMin + next() * (rMax - rMin)),
		o: round(0.35 + next() * 0.65)
	}));
}

export function starTile(stars: Star[], color: string): string {
	const circles = stars.map((s) => `<circle cx="${s.x}" cy="${s.y}" r="${s.r}" fill-opacity="${s.o}"/>`).join('');
	const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${TILE.w}" height="${TILE.h}"><g fill="${color}">${circles}</g></svg>`;
	return `url("data:image/svg+xml,${encodeURIComponent(svg)}")`;
}

export function backgroundAnimated(setting: boolean, reducedMotion: boolean): boolean {
	return setting && !reducedMotion;
}

/** Far → near: more, smaller, dimmer, slower at the back. */
export const LAYERS: { seed: number; count: number; r: [number, number]; color: string; seconds: number }[] = [
	{ seed: 11, count: 260, r: [0.4, 0.8], color: '#ffffff', seconds: 90 },
	{ seed: 23, count: 110, r: [0.7, 1.1], color: '#dbe7ff', seconds: 55 },
	{ seed: 37, count: 40, r: [1.1, 1.6], color: '#ffeccc', seconds: 35 }
];

/** Layer colours: the fine far layer stays white; the two nearer layers take the tint (sub-project 5). */
export function layerColors(tint: string | null): string[] {
	return LAYERS.map((l, i) => (tint && i > 0 ? tint : l.color));
}

export function nebula(tint: string | null): string {
	if (!tint) {
		return 'radial-gradient(ellipse 50% 35% at 70% 30%, rgba(59, 47, 107, 0.25), transparent 70%), ' +
			'radial-gradient(ellipse 45% 45% at 20% 75%, rgba(29, 74, 107, 0.25), transparent 70%)';
	}
	return `radial-gradient(ellipse 50% 35% at 70% 30%, ${tint}33, transparent 70%), ` +
		`radial-gradient(ellipse 45% 45% at 20% 75%, ${tint}26, transparent 70%)`;
}
