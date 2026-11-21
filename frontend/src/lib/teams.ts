import type { TileView } from './materials';
import type { Character, MemberDraft, Team, TeamMaterial, TeamMember } from './types';

export const BUILD_TAG_ID = 1;
export const TAG_COLORS = ['orange', 'red', 'yellow', 'green', 'teal', 'blue', 'purple', 'pink'] as const;
export const TAG_HEX: Record<string, string> = {
	orange: '#d9822b', red: '#d64545', yellow: '#c9a227', green: '#3f9c5a',
	teal: '#2f9c95', blue: '#3d7bd9', purple: '#8a5cd6', pink: '#d65c9c'
};
export const MAX_MEMBERS = 4;

export interface TeamFilter { tagIds: number[]; untagged: boolean }
const FILTER_KEY = 'gt.teamFilter';

export function emptyTeamFilter(): TeamFilter {
	return { tagIds: [], untagged: false };
}

export function toggleTag(f: TeamFilter, id: number): TeamFilter {
	const tagIds = f.tagIds.includes(id) ? f.tagIds.filter((t) => t !== id) : [...f.tagIds, id];
	return { tagIds, untagged: false };
}

export function toggleUntagged(f: TeamFilter): TeamFilter {
	return { tagIds: [], untagged: !f.untagged };
}

export function filterTeams(teams: Team[], f: TeamFilter): Team[] {
	if (f.untagged) return teams.filter((t) => t.tags.length === 0);
	return teams.filter((t) => f.tagIds.every((id) => t.tags.some((tag) => tag.id === id)));
}

export function loadTeamFilter(): TeamFilter {
	try {
		const raw = localStorage.getItem(FILTER_KEY);
		if (raw) {
			const v = JSON.parse(raw);
			if (Array.isArray(v.tagIds)) return { tagIds: v.tagIds.filter(Number.isInteger), untagged: !!v.untagged };
		}
	} catch {
		/* storage blocked or corrupt: default */
	}
	return emptyTeamFilter();
}

export function saveTeamFilter(f: TeamFilter): void {
	try {
		localStorage.setItem(FILTER_KEY, JSON.stringify(f));
	} catch {
		/* ignore */
	}
}

/** A character matches when one of its teams carries every selected tag. */
export function matchesTeamTags(teamTags: number[][], selected: number[]): boolean {
	if (selected.length === 0) return true;
	return teamTags.some((tags) => selected.every((id) => tags.includes(id)));
}

export function addMember(members: MemberDraft[], id: number): MemberDraft[] {
	if (members.length >= MAX_MEMBERS || members.some((m) => m.character_id === id)) return members;
	return [...members, { character_id: id, role: '' }];
}

export function removeMember(members: MemberDraft[], index: number): MemberDraft[] {
	return members.filter((_m, i) => i !== index);
}

export function moveItem<T>(list: T[], from: number, to: number): T[] {
	if (from < 0 || from >= list.length || to < 0 || to >= list.length || from === to) return list;
	const copy = [...list];
	const [item] = copy.splice(from, 1);
	copy.splice(to, 0, item);
	return copy;
}

/** Names of members a save would raise to Build (mirrors app.teams.store.save_team). */
export function willRaise(
	chars: Character[],
	draft: { members: MemberDraft[]; hasBuild: boolean },
	original: { memberIds: number[]; hadBuild: boolean }
): string[] {
	if (!draft.hasBuild) return [];
	const byId = new Map(chars.map((c) => [c.id, c]));
	return draft.members
		.filter((m) => !original.hadBuild || !original.memberIds.includes(m.character_id))
		.map((m) => byId.get(m.character_id))
		.filter((c): c is Character => !!c && c.goal !== 'build')
		.map((c) => c.name);
}

export function raisedMessage(n: number): string {
	return `Raised ${n} ${n === 1 ? 'character' : 'characters'} to Build`;
}

export function memberLine(m: TeamMember): string {
	if (!m.owned || m.level === null) return '';
	return m.talents ? `Lv ${m.level} · ${m.talents.normal}/${m.talents.skill}/${m.talents.burst}` : `Lv ${m.level}`;
}

export function weaponLine(m: TeamMember): string {
	return m.weapon ? `Lv ${m.weapon.level} R${m.weapon.refinement}` : '';
}

export function teamTileView(m: TeamMaterial): TileView {
	const hints = [m.craftable > 0 ? `craft ${m.craftable}` : null, m.shared ? 'shared' : null].filter(Boolean);
	const hint = hints.length ? hints.join(' · ') : null;
	if (m.short > 0) {
		return { main: `${m.need - m.short}/${m.need}`, badge: m.to_farm > 0 ? `−${m.to_farm}` : null, hint, tone: 'short' };
	}
	return { main: `✓ ${m.need}`, badge: null, hint, tone: 'met' };
}

/** The panel lists only what is still short for the team. */
export function farmRows(rows: TeamMaterial[]): TeamMaterial[] {
	return rows.filter((r) => r.short > 0);
}
