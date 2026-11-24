import type { IconName } from './icons';
import type { ShowcaseEntry, StatTile } from './types';

export const SHOWCASE_MAX = 8;
export const BOSSES_SHOWN = 6;

export const TILE_ICON: Record<string, IconName> = {
	characters: 'characters', friendship: 'friendship', waypoint: 'waypoint', domain: 'domain', abyss: 'abyss',
	chest: 'chest', oculus: 'oculus'
};

export function toggleId(ids: number[], id: number, max = SHOWCASE_MAX): number[] {
	if (ids.includes(id)) return ids.filter((i) => i !== id);
	return ids.length >= max ? ids : [...ids, id];
}

export function moveId(ids: number[], index: number, delta: -1 | 1): number[] {
	const j = index + delta;
	if (j < 0 || j >= ids.length) return ids;
	const out = [...ids];
	[out[index], out[j]] = [out[j], out[index]];
	return out;
}

export function ringDash(pct: number, r = 15): string {
	const c = 2 * Math.PI * r;
	return `${((Math.max(0, Math.min(100, pct)) / 100) * c).toFixed(1)} ${c.toFixed(1)}`;
}

export function tileTitle(t: StatTile): string {
	return t.detail?.map((d) => `${d.label} ${d.value}`).join(' · ') ?? '';
}

export function talentLine(t: ShowcaseEntry['talents']): string {
	return [t.normal, t.skill, t.burst].map((v) => v ?? '—').join(' / ');
}

export function topBosses<T>(bosses: T[], all: boolean): T[] {
	return all ? bosses : bosses.slice(0, BOSSES_SHOWN);
}
