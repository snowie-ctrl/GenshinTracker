import { describe, expect, it } from 'vitest';
import type { Character, Team, TeamMaterial, TeamMember } from './types';
import {
	addMember, emptyTeamFilter, farmRows, filterActive, filterTeams, keepKnownTags, matchesTeamTags, memberLine,
	moveItem, pruneTeamFilter, raisedMessage, removeMember, teamErrorField, teamTileView, toggleTag, toggleUntagged,
	validateTeam, weaponLine, willRaise
} from './teams';

describe('deleted tags', () => {
	it('drops selected tag ids that no longer exist', () => {
		expect(keepKnownTags([1, 5, 7], [1, 7, 9])).toEqual([1, 7]);
		const f = { tagIds: [1, 5], untagged: false };
		expect(pruneTeamFilter(f, [1, 2])).toEqual({ tagIds: [1], untagged: false });
	});
	it('returns the same filter when nothing was pruned', () => {
		const f = { tagIds: [1, 2], untagged: false };
		expect(pruneTeamFilter(f, [1, 2, 3])).toBe(f);
		const u = { tagIds: [], untagged: true };
		expect(pruneTeamFilter(u, [])).toBe(u);
	});
});

describe('team editor errors', () => {
	it('checks name then members before saving', () => {
		expect(validateTeam('  ', 0)).toEqual({ field: 'name', message: 'Team name is required' });
		expect(validateTeam('Dendro', 0)).toEqual({ field: 'members', message: 'A team needs 1 to 4 members' });
		expect(validateTeam('Dendro', 2)).toBeNull();
	});
	it('places a server 422 next to the field it is about', () => {
		expect(teamErrorField('Team name can be at most 60 characters')).toBe('name');
		expect(teamErrorField('Notes can be at most 2000 characters')).toBe('notes');
		expect(teamErrorField('A team needs 1 to 4 members')).toBe('members');
		expect(teamErrorField('A character can be in a team only once')).toBe('members');
		expect(teamErrorField('Unknown character 10000099')).toBe('members');
		expect(teamErrorField('Role can be at most 40 characters')).toBe('members');
		expect(teamErrorField('Unknown tag')).toBe('tags');
		expect(teamErrorField('Tag name can be at most 30 characters')).toBe('tags');
		expect(teamErrorField('Tag name is required')).toBe('tags');
		expect(teamErrorField('Something else')).toBeNull();
	});
});

describe('filterActive', () => {
	it('is on for any tag or Untagged selection', () => {
		expect(filterActive(emptyTeamFilter())).toBe(false);
		expect(filterActive({ tagIds: [2], untagged: false })).toBe(true);
		expect(filterActive({ tagIds: [], untagged: true })).toBe(true);
	});
});

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
		targets: null, status: 'obtained', prefarming: false, progress: null, planned_weapon_id: null, team_tags: [], release_at: null
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

import { changeMessage, loweredMessage, memberLookup, slantInset, talentParts, willLower } from './teams';

const lm = (id: number, name: string, goal: 'build' | 'want' | 'none' = 'build') =>
	({ id, name, goal }) as unknown as TeamMember;
const lt = (id: number, build: boolean, members: TeamMember[]) =>
	({ id, has_build_tag: build, members }) as unknown as Team;

describe('willLower', () => {
	const teams = [lt(1, true, [lm(10, 'Ben'), lm(11, 'Fur'), lm(12, 'Xq', 'want')]), lt(2, true, [lm(11, 'Fur')]), lt(3, false, [lm(10, 'Ben')])];
	const look = memberLookup(teams);
	it('switch off: every Build member not in another Build team', () => {
		expect(willLower(teams, look, 1, { memberIds: [10, 11, 12], hasBuild: false })).toEqual(['Ben']);
	});
	it('remove a member from a Build team', () => {
		expect(willLower(teams, look, 1, { memberIds: [11, 12], hasBuild: true })).toEqual(['Ben']);
	});
	it('delete', () => {
		expect(willLower(teams, look, 1, null)).toEqual(['Ben']);
	});
	it('team without Build or new team lowers nothing', () => {
		expect(willLower(teams, look, 3, null)).toEqual([]);
		expect(willLower(teams, look, null, { memberIds: [10], hasBuild: false })).toEqual([]);
	});
});

describe('messages and geometry', () => {
	it('builds change messages', () => {
		expect(loweredMessage(1)).toBe('Moved 1 character off Build');
		expect(changeMessage('Saved', [1], [2, 3])).toBe('Saved · Raised 1 character to Build · Moved 2 characters off Build');
		expect(changeMessage('Saved', [], [])).toBe('Saved');
	});
	it('marks crowned talents', () => {
		expect(talentParts({ normal: 10, skill: 9, burst: 10 })).toEqual([
			{ value: 10, crowned: true }, { value: 9, crowned: false }, { value: 10, crowned: true }]);
		expect(talentParts(null)).toEqual([]);
	});
	it('computes the slant inset', () => {
		expect(slantInset(100)).toBe(33);
		expect(slantInset(330)).toBe(108);
		expect(slantInset(100, 0)).toBe(0);
	});
});
