import { describe, expect, it } from 'vitest';
import {
	DEFAULT_ARTIFACT_FILTER, filterArtifacts, filterWeapons, holderLabel, importSummaryText, isUnequipped,
	ownedLabel, scanAgeNote, statName, statValue
} from './good';
import type { GoodArtifact, GoodSummary, GoodWeapon } from './types';

const bennett = { id: 10000032, name: 'Bennett', slug: 'bennett', icon: 'UI_AvatarIcon_Bennett' };
const weapon = (over: Partial<GoodWeapon>): GoodWeapon => ({
	id: 1, weapon_id: 11401, name: 'Favonius Sword', icon: 'UI_W', rarity: 4, weapon_type: 'Sword', level: 90,
	ascension: 6, refinement: 3, lock: false, location: null, holder: null, ...over
});
const artifact = (over: Partial<GoodArtifact>): GoodArtifact => ({
	id: 1, set_id: 15007, set_name: 'Noblesse Oblige', icon: 'UI_R', slot: 'flower', rarity: 5, level: 20,
	main_stat: 'hp', substats: [], lock: false, location: null, holder: null, ...over
});

describe('stats', () => {
	it('names and formats GOOD stat keys', () => {
		expect(statName('critRate_')).toBe('CRIT Rate');
		expect(statName('hydro_dmg_')).toBe('Hydro DMG Bonus');
		expect(statName('mystery')).toBe('mystery');
		expect(statValue('critRate_', 3.9)).toBe('3.9%');
		expect(statValue('atk', 18.0)).toBe('18');
		expect(statValue('eleMas', 23)).toBe('23');
	});
});

describe('holders', () => {
	it('distinguishes unequipped from an unknown holder', () => {
		expect(holderLabel(weapon({ holder: bennett, location: 'Bennett' }))).toBe('Bennett');
		expect(holderLabel(weapon({ location: 'SomeNewCharacter' }))).toBe('Equipped');
		expect(holderLabel(weapon({}))).toBe('Unequipped');
		expect(isUnequipped(weapon({ location: 'SomeNewCharacter' }))).toBe(false);
		expect(isUnequipped(weapon({}))).toBe(true);
	});
});

describe('filters', () => {
	const ws = [weapon({ id: 1, holder: bennett, location: 'Bennett' }),
		weapon({ id: 2, name: 'Mistsplitter Reforged', rarity: 5 }),
		weapon({ id: 3, name: 'Slingshot', weapon_type: 'Bow', rarity: 3 })];
	it('filters weapons by type, rarity, unequipped and name', () => {
		const base = { type: '', rarity: 0, unequippedOnly: false, query: '' };
		expect(filterWeapons(ws, { ...base, type: 'Sword' }).map((w) => w.id)).toEqual([1, 2]);
		expect(filterWeapons(ws, { ...base, rarity: 5 }).map((w) => w.id)).toEqual([2]);
		expect(filterWeapons(ws, { ...base, unequippedOnly: true }).map((w) => w.id)).toEqual([2, 3]);
		expect(filterWeapons(ws, { ...base, query: 'mist' }).map((w) => w.id)).toEqual([2]);
	});
	const as = [artifact({ id: 1 }), artifact({ id: 2, slot: 'goblet', main_stat: 'hydro_dmg_' }),
		artifact({ id: 3, rarity: 3, set_id: 15001 }), artifact({ id: 4, location: 'X' })];
	it('filters artifacts; default hides below 4★', () => {
		expect(filterArtifacts(as, DEFAULT_ARTIFACT_FILTER).map((a) => a.id)).toEqual([1, 2, 4]);
		expect(filterArtifacts(as, { ...DEFAULT_ARTIFACT_FILTER, slot: 'goblet' }).map((a) => a.id)).toEqual([2]);
		expect(filterArtifacts(as, { ...DEFAULT_ARTIFACT_FILTER, mainStat: 'hp' }).map((a) => a.id)).toEqual([1, 4]);
		expect(filterArtifacts(as, { ...DEFAULT_ARTIFACT_FILTER, unequippedOnly: true }).map((a) => a.id)).toEqual([1, 2]);
		expect(filterArtifacts(as, { ...DEFAULT_ARTIFACT_FILTER, minRarity: 1, setId: 15001 }).map((a) => a.id)).toEqual([3]);
	});
});

describe('labels', () => {
	const summary = (over: Partial<GoodSummary['counts']['materials']>, wUnmatched = 1): GoodSummary => ({
		imported_at: '2026-11-22T12:00:00Z', source: 'X',
		counts: { materials: { matched: 412, ignored: 90, unmatched: 2, ...over },
			weapons: { matched: 318, unmatched: wUnmatched }, artifacts: { matched: 1804, unmatched: 0 } },
		unmatched: []
	});
	it('summarises an import', () => {
		expect(importSummaryText(summary({}))).toBe('Imported 412 materials, 318 weapons, 1804 artifacts. 3 keys not recognised.');
		expect(importSummaryText(summary({ unmatched: 0 }, 0))).toBe('Imported 412 materials, 318 weapons, 1804 artifacts.');
		expect(importSummaryText(summary({ unmatched: 11 }))).toContain('Try Refresh game data in Settings.');
	});
	it('warns about old scans only after 30 days', () => {
		const now = Date.parse('2026-11-22T12:00:00Z');
		expect(scanAgeNote('2026-11-01T12:00:00Z', now)).toBeNull();
		expect(scanAgeNote('2026-10-01T12:00:00Z', now)).toBe('scan is 52 days old');
	});
	it('labels owned weapons', () => {
		expect(ownedLabel({ count: 2, best_level: 90, best_refinement: 3 })).toBe('owned · Lv 90 · R3');
	});
});
