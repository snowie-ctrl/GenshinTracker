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

function elementRank(e: string | null): number {
	const i = ELEMENTS.indexOf(e ?? '');
	return i === -1 ? ELEMENTS.length : i;
}

export function groupCharacters(chars: Character[], f: Filters): Record<Status, Character[]> {
	const groups: Record<Status, Character[]> = { building: [], obtained: [], wanted: [], unobtained: [] };
	for (const c of chars) if (matches(c, f)) groups[c.status].push(c);
	groups.building.sort((a, b) => (a.progress ?? 0) - (b.progress ?? 0) || a.name.localeCompare(b.name));
	const byRarity = (a: Character, b: Character) =>
		b.rarity - a.rarity || elementRank(a.element) - elementRank(b.element) || a.name.localeCompare(b.name);
	groups.obtained.sort(byRarity);
	groups.wanted.sort(byRarity);
	groups.unobtained.sort(byRarity);
	return groups;
}
