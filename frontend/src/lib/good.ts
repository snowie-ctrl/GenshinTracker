import type { ArtifactSlot, CharRef, GoodArtifact, GoodSummary, GoodWeapon, OwnedWeapon } from './types';

export const ARTIFACT_PAGE = 100;
export const SLOTS: ArtifactSlot[] = ['flower', 'plume', 'sands', 'goblet', 'circlet'];
export const SLOT_NAMES: Record<ArtifactSlot, string> = {
	flower: 'Flower', plume: 'Plume', sands: 'Sands', goblet: 'Goblet', circlet: 'Circlet'
};
export const STAT_NAMES: Record<string, string> = {
	hp: 'HP', hp_: 'HP', atk: 'ATK', atk_: 'ATK', def: 'DEF', def_: 'DEF', eleMas: 'Elemental Mastery',
	enerRech_: 'Energy Recharge', critRate_: 'CRIT Rate', critDMG_: 'CRIT DMG', heal_: 'Healing Bonus',
	physical_dmg_: 'Physical DMG Bonus', anemo_dmg_: 'Anemo DMG Bonus', geo_dmg_: 'Geo DMG Bonus',
	electro_dmg_: 'Electro DMG Bonus', hydro_dmg_: 'Hydro DMG Bonus', pyro_dmg_: 'Pyro DMG Bonus',
	cryo_dmg_: 'Cryo DMG Bonus', dendro_dmg_: 'Dendro DMG Bonus'
};

export function statName(key: string): string {
	const base = STAT_NAMES[key] ?? key;
	return ['hp_', 'atk_', 'def_'].includes(key) ? `${base}%` : base;
}

export function statValue(key: string, value: number): string {
	return key.endsWith('_') ? `${Math.round(value * 10) / 10}%` : `${Math.round(value)}`;
}

type Held = { holder: CharRef | null; location: string | null };
export function isUnequipped(item: Held): boolean {
	return !item.holder && !item.location;
}
export function holderLabel(item: Held): string {
	return item.holder?.name ?? (item.location ? 'Equipped' : 'Unequipped');
}

export interface WeaponFilter { type: string; rarity: number; unequippedOnly: boolean; query: string }
export function filterWeapons(ws: GoodWeapon[], f: WeaponFilter): GoodWeapon[] {
	const q = f.query.trim().toLowerCase();
	return ws.filter((w) =>
		(!f.type || w.weapon_type === f.type) && (!f.rarity || w.rarity === f.rarity) &&
		(!f.unequippedOnly || isUnequipped(w)) && (!q || w.name.toLowerCase().includes(q)));
}

export interface ArtifactFilter { setId: number; slot: ArtifactSlot | ''; mainStat: string; unequippedOnly: boolean; minRarity: number }
export const DEFAULT_ARTIFACT_FILTER: ArtifactFilter = { setId: 0, slot: '', mainStat: '', unequippedOnly: false, minRarity: 4 };
export function filterArtifacts(as: GoodArtifact[], f: ArtifactFilter): GoodArtifact[] {
	return as.filter((a) =>
		(!f.setId || a.set_id === f.setId) && (!f.slot || a.slot === f.slot) &&
		(!f.mainStat || a.main_stat === f.mainStat) && (!f.unequippedOnly || isUnequipped(a)) &&
		a.rarity >= f.minRarity);
}

export function importSummaryText(s: GoodSummary): string {
	const c = s.counts;
	const unknown = c.materials.unmatched + c.weapons.unmatched + c.artifacts.unmatched;
	let text = `Imported ${c.materials.matched} materials, ${c.weapons.matched} weapons, ${c.artifacts.matched} artifacts.`;
	if (unknown > 0) text += ` ${unknown} ${unknown === 1 ? 'key' : 'keys'} not recognised.`;
	if (c.materials.unmatched + c.weapons.unmatched > 10) text += ' Try Refresh game data in Settings.';
	return text;
}

const DAY = 86_400_000;
export function scanAgeNote(importedAt: string, now: number): string | null {
	const days = Math.floor((now - Date.parse(importedAt)) / DAY);
	return days > 30 ? `scan is ${days} days old` : null;
}

export function ownedLabel(o: OwnedWeapon): string {
	return `owned · Lv ${o.best_level} · R${o.best_refinement}`;
}
