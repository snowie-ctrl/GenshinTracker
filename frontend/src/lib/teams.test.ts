import { describe, expect, it } from 'vitest';
import type { Character, Team, TeamMaterial, TeamMember } from './types';
import {
	addMember, emptyTeamFilter, farmRows, filterTeams, matchesTeamTags, memberLine, moveItem, raisedMessage,
	removeMember, teamTileView, toggleTag, toggleUntagged, weaponLine, willRaise
} from './teams';

const tag = (id: number, name: string) => ({ id, name, color: 'red', builtin: id === 1 });

function team(id: number, tagIds: number[]): Team {
	return {
		id, name: `T${id}`, notes: '', sort_order: id, tags: tagIds.map((t) => tag(t, `t${t}`)),
		has_build_tag: tagIds.includes(1), members: [], shortfall: null, progress: null
	};
}

function char(id: number, goal: Character['goal'], name = `C${id}`): Character {
	return {
		id, slug: `c${id}`, name, rarity: 4, element: 'Pyro', weapon_type: 'Sword', icon: null, splash: null,
		owned: true, level: 80, constellation: 0, friendship: 10, talents: null, weapon: null, goal,
		targets: null, status: 'obtained', prefarming: false, progress: null, planned_weapon_id: null, team_tags: []
	};
}

describe('team filter', () => {
	const teams = [team(1, [1, 2]), team(2, [2]), team(3, [])];
	it('All shows everything', () => expect(filterTeams(teams, emptyTeamFilter()).map((t) => t.id)).toEqual([1, 2, 3]));
	it('tags combine with AND', () => {
		expect(filterTeams(teams, { tagIds: [2], untagged: false }).map((t) => t.id)).toEqual([1, 2]);
		expect(filterTeams(teams, { tagIds: [1, 2], untagged: false }).map((t) => t.id)).toEqual([1]);
	});
	it('Untagged and tags exclude each other', () => {
		const u = toggleUntagged(toggleTag(emptyTeamFilter(), 2));
		expect(u).toEqual({ tagIds: [], untagged: true });
		expect(filterTeams(teams, u).map((t) => t.id)).toEqual([3]);
		expect(toggleTag(u, 1)).toEqual({ tagIds: [1], untagged: false });
		expect(toggleTag({ tagIds: [1], untagged: false }, 1)).toEqual({ tagIds: [], untagged: false });
	});
	it('character tag match needs one team with all selected tags', () => {
		expect(matchesTeamTags([[1, 2], [3]], [])).toBe(true);
		expect(matchesTeamTags([[1, 2], [3]], [1, 2])).toBe(true);
		expect(matchesTeamTags([[1], [2]], [1, 2])).toBe(false);
		expect(matchesTeamTags([], [1])).toBe(false);
	});
});

describe('slots', () => {
	it('adds to the first free slot, ignores duplicates and a full team', () => {
		let m = addMember([], 5);
		m = addMember(m, 6);
		expect(addMember(m, 5)).toEqual(m);
		const full = [5, 6, 7, 8].reduce((acc, id) => addMember(acc, id), [] as { character_id: number; role: string }[]);
		expect(addMember(full, 9)).toEqual(full);
		expect(m).toEqual([{ character_id: 5, role: '' }, { character_id: 6, role: '' }]);
	});
	it('removes and compacts, moves', () => {
		const m = [5, 6, 7].map((id) => ({ character_id: id, role: '' }));
		expect(removeMember(m, 1).map((x) => x.character_id)).toEqual([5, 7]);
		expect(moveItem([1, 2, 3], 0, 2)).toEqual([2, 3, 1]);
		expect(moveItem([1, 2, 3], 2, 0)).toEqual([3, 1, 2]);
		expect(moveItem([1, 2, 3], 0, 5)).toEqual([1, 2, 3]);
	});
});

describe('raise preview', () => {
	const chars = [char(1, 'none', 'Xiangling'), char(2, 'build', 'Bennett'), char(3, 'want', 'Kazuha')];
	const members = [1, 2, 3].map((id) => ({ character_id: id, role: '' }));
	it('adding Build raises every non-build member', () => {
		expect(willRaise(chars, { members, hasBuild: true }, { memberIds: [1, 2, 3], hadBuild: false }))
			.toEqual(['Xiangling', 'Kazuha']);
	});
	it('an existing Build team raises only new members', () => {
		expect(willRaise(chars, { members, hasBuild: true }, { memberIds: [1, 2], hadBuild: true })).toEqual(['Kazuha']);
	});
	it('no Build tag raises nobody', () => {
		expect(willRaise(chars, { members, hasBuild: false }, { memberIds: [], hadBuild: false })).toEqual([]);
	});
	it('messages', () => {
		expect(raisedMessage(1)).toBe('Raised 1 character to Build');
		expect(raisedMessage(3)).toBe('Raised 3 characters to Build');
	});
});

describe('text helpers', () => {
	const m = {
		id: 1, name: 'Bennett', slug: 'bennett', icon: null, element: 'Pyro', rarity: 4, owned: true, goal: 'build',
		status: 'building', prefarming: false, level: 80, talents: { normal: 6, skill: 8, burst: 8 },
		weapon: { name: 'Sword', icon: '', rarity: 4, level: 90, refinement: 5 }, progress: 0.5, role: '',
		artifact_line: '4pc Noblesse Oblige', not_building: false, not_calculated: false
	} as TeamMember;
	it('member and weapon lines', () => {
		expect(memberLine(m)).toBe('Lv 80 · 6/8/8');
		expect(memberLine({ ...m, owned: false, level: null, talents: null })).toBe('');
		expect(weaponLine(m)).toBe('Lv 90 R5');
		expect(weaponLine({ ...m, weapon: null })).toBe('');
	});
	it('tile view and farm rows', () => {
		const row: TeamMaterial = {
			id: 1, name: 'Guide', icon: '', rarity: 3, category: 'talent', category_label: 'Talent books',
			need: 9, short: 1, craftable: 1, to_farm: 0, shared: true
		};
		expect(teamTileView(row)).toEqual({ main: '8/9', badge: null, hint: 'craft 1 · shared', tone: 'short' });
		expect(teamTileView({ ...row, short: 0, craftable: 0 })).toEqual({ main: '✓ 9', badge: null, hint: 'shared', tone: 'met' });
		expect(teamTileView({ ...row, to_farm: 2, short: 2, craftable: 0, shared: false }).badge).toBe('−2');
		expect(farmRows([row, { ...row, id: 2, short: 0 }]).map((r) => r.id)).toEqual([1]);
	});
});
