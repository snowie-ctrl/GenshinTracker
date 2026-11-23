import { matchesTeamTags } from './teams';
import type { Character, Goal, Status } from './types';

export const SECTIONS: { status: Status; label: string }[] = [
	{ status: 'building', label: 'Actively building' },
	{ status: 'obtained', label: 'Obtained' },
	{ status: 'wanted', label: 'Wanted' },
	{ status: 'unobtained', label: 'Unobtained' }
];
export const ELEMENTS = ['Pyro', 'Hydro', 'Anemo', 'Electro', 'Dendro', 'Cryo', 'Geo'];
export const WEAPON_TYPES = ['Sword', 'Claymore', 'Polearm', 'Bow', 'Catalyst'];

export function deriveStatus(owned: boolean, goal: Goal): { status: Status; prefarming: boolean } {
	if (owned) return { status: goal === 'build' ? 'building' : 'obtained', prefarming: false };
	if (goal === 'none') return { status: 'unobtained', prefarming: false };
	return { status: 'wanted', prefarming: goal === 'build' };
}

export function statusLine(c: Character): string {
	switch (c.status) {
		case 'building':
			return `${Math.round((c.progress ?? 0) * 100)}%`;
		case 'obtained':
			return `Lv ${c.level} · C${c.constellation}`;
		case 'wanted':
			return c.prefarming ? 'Pre-farming' : 'Wanted';
		default:
			return '';
	}
}

export function progressTooltip(c: Character): string {
	if (!c.targets) return '';
	const t = c.talents;
	const now = t ? `${t.normal}/${t.skill}/${t.burst}` : '?/?/?';
	return `Lv ${c.level ?? '?'}→${c.targets.level} · ${now} → ${c.targets.normal}/${c.targets.skill}/${c.targets.burst}`;
}

export interface Filters { elements: string[]; weapons: string[]; rarities: number[]; search: string; teamTags: number[] }

export function emptyFilters(): Filters {
	return { elements: [], weapons: [], rarities: [], search: '', teamTags: [] };
}

export function matches(c: Character, f: Filters): boolean {
	if (f.elements.length && !f.elements.includes(c.element ?? '')) return false;
	if (f.weapons.length && !f.weapons.includes(c.weapon_type ?? '')) return false;
	if (f.rarities.length && !f.rarities.includes(c.rarity)) return false;
	if (!matchesTeamTags(c.team_tags ?? [], f.teamTags)) return false;
	const q = f.search.trim().toLowerCase();
	return !q || c.name.toLowerCase().includes(q);
}

export interface SortKeys { az: boolean; rarity: boolean; level: boolean }
export const DEFAULT_SORT: SortKeys = { az: true, rarity: true, level: false };

const levelOf = (c: Character) => (c.owned ? c.level ?? 0 : 0);

export function sortCharacters(chars: Character[], k: SortKeys): Character[] {
	return [...chars].sort((a, b) =>
		(k.rarity ? b.rarity - a.rarity : 0) ||
		(k.level ? levelOf(b) - levelOf(a) : 0) ||
		(k.az ? a.name.localeCompare(b.name)
			: (b.release_at ?? '').localeCompare(a.release_at ?? '') || a.name.localeCompare(b.name)));
}

export function groupCharacters(chars: Character[], f: Filters, keys: SortKeys = DEFAULT_SORT): Record<Status, Character[]> {
	const groups: Record<Status, Character[]> = { building: [], obtained: [], wanted: [], unobtained: [] };
	for (const c of chars) if (matches(c, f)) groups[c.status].push(c);
	for (const s of Object.keys(groups) as Status[]) groups[s] = sortCharacters(groups[s], keys);
	return groups;
}
