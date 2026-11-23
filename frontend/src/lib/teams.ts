import type { TileView } from './materials';
import type { Character, Goal, MemberDraft, Talents, Team, TeamMaterial, TeamMember } from './types';

export const BUILD_TAG_ID = 1;
export const TAG_COLORS = ['orange', 'red', 'yellow', 'green', 'teal', 'blue', 'purple', 'pink', 'navy', 'gold'] as const;
export const TAG_HEX: Record<string, string> = {
	orange: '#d9822b', red: '#d64545', yellow: '#c9a227', green: '#3f9c5a',
	teal: '#2f9c95', blue: '#3d7bd9', purple: '#8a5cd6', pink: '#d65c9c', navy: '#2a3f8f', gold: '#a9842c'
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

export function filterActive(f: TeamFilter): boolean {
	return f.untagged || f.tagIds.length > 0;
}

/** Selected tag ids that still exist (a tag may have been deleted). */
export function keepKnownTags(selected: number[], known: number[]): number[] {
	return selected.filter((id) => known.includes(id));
}

/** The filter without deleted tags; the same object when nothing changed. */
export function pruneTeamFilter(f: TeamFilter, known: number[]): TeamFilter {
	const tagIds = keepKnownTags(f.tagIds, known);
	return tagIds.length === f.tagIds.length ? f : { ...f, tagIds };
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

export type TeamField = 'name' | 'notes' | 'members' | 'tags';
export interface FieldError { field: TeamField | null; message: string }

/** The editor's own checks before saving (the server repeats them). */
export function validateTeam(name: string, memberCount: number): FieldError | null {
	if (!name.trim()) return { field: 'name', message: 'Team name is required' };
	if (memberCount === 0) return { field: 'members', message: 'A team needs 1 to 4 members' };
	return null;
}

/** Which editor field a server 422 message is about (mirrors app.teams.store messages). */
export function teamErrorField(message: string): TeamField | null {
	if (message.startsWith('Team name')) return 'name';
	if (message.startsWith('Notes')) return 'notes';
	// anchored: "Tag name can be at most 30 characters" is about tags, not members
	if (/^(Tag\b|Unknown tag\b)/i.test(message)) return 'tags';
	if (/^(Role\b|A team needs|A character\b|Unknown character\b)/i.test(message)) return 'members';
	return null;
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

export const RIBBON_DEG = 18;

export interface GoalRef { name: string; goal: Goal }

export function memberLookup(teams: Team[]): Map<number, GoalRef> {
	const out = new Map<number, GoalRef>();
	for (const t of teams) for (const m of t.members) out.set(m.id, { name: m.name, goal: m.goal });
	return out;
}

export function charLookup(chars: Character[]): Map<number, GoalRef> {
	return new Map(chars.map((c) => [c.id, { name: c.name, goal: c.goal }]));
}

/** Names of members a change would move off Build (mirrors app.teams.store / goals.lower_from_build).
 *  draft = null means the team is deleted. */
export function willLower(
	teams: Team[], lookup: Map<number, GoalRef>, teamId: number | null,
	draft: { memberIds: number[]; hasBuild: boolean } | null
): string[] {
	const team = teams.find((t) => t.id === teamId);
	if (!team || !team.has_build_tag) return [];
	const old = team.members.map((x) => x.id);
	const candidates = draft === null || !draft.hasBuild
		? [...new Set([...(draft?.memberIds ?? []), ...old])]
		: old.filter((id) => !draft.memberIds.includes(id));
	const covered = new Set(teams.filter((t) => t.id !== teamId && t.has_build_tag).flatMap((t) => t.members.map((x) => x.id)));
	return candidates
		.filter((id) => lookup.get(id)?.goal === 'build' && !covered.has(id))
		.map((id) => lookup.get(id)!.name);
}

export function loweredMessage(n: number): string {
	return `Moved ${n} ${n === 1 ? 'character' : 'characters'} off Build`;
}

export function changeMessage(prefix: string, raised: number[], lowered: number[]): string {
	return [prefix, raised.length ? raisedMessage(raised.length) : null, lowered.length ? loweredMessage(lowered.length) : null]
		.filter(Boolean).join(' · ');
}

export function talentParts(t: Talents | null): { value: number; crowned: boolean }[] {
	return t ? [t.normal, t.skill, t.burst].map((value) => ({ value, crowned: value >= 10 })) : [];
}

/** Horizontal offset of a slanted edge over `heightPx` (keeps text clear of the ribbon edge). */
export function slantInset(heightPx: number, deg: number = RIBBON_DEG): number {
	return Math.ceil(heightPx * Math.tan((deg * Math.PI) / 180));
}
