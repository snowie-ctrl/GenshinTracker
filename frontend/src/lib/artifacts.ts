import type { ArtifactSetOption, ArtifactTarget, MainSlot } from './types';

export const MAIN_SLOTS: MainSlot[] = ['sands', 'goblet', 'circlet'];
const ELEMENTS = ['pyro', 'hydro', 'electro', 'cryo', 'anemo', 'geo', 'dendro'];
export const SLOT_OPTIONS: Record<MainSlot, string[]> = {
	sands: ['hp%', 'atk%', 'def%', 'em', 'er'],
	goblet: ['hp%', 'atk%', 'def%', 'em', ...ELEMENTS, 'phys'],
	circlet: ['hp%', 'atk%', 'def%', 'em', 'crit_rate', 'crit_dmg', 'heal']
};
export const SUB_KEYS = ['crit_rate', 'crit_dmg', 'er', 'em', 'atk%', 'hp%', 'def%', 'atk', 'hp', 'def'];
export const STAT_LABELS: Record<string, string> = {
	hp: 'HP', atk: 'ATK', def: 'DEF', 'hp%': 'HP%', 'atk%': 'ATK%', 'def%': 'DEF%', em: 'EM', er: 'ER',
	crit_rate: 'CRIT Rate', crit_dmg: 'CRIT DMG', heal: 'Healing', phys: 'Physical',
	pyro: 'Pyro', hydro: 'Hydro', electro: 'Electro', cryo: 'Cryo', anemo: 'Anemo', geo: 'Geo', dendro: 'Dendro'
};

export function emptyTarget(): ArtifactTarget {
	return { sets: [], main: { sands: [], goblet: [], circlet: [] }, subs: [] };
}

export function toggleStat(list: string[], key: string): string[] {
	return list.includes(key) ? list.filter((k) => k !== key) : [...list, key];
}

export function moveSub(order: string[], from: number, to: number): string[] {
	if (from < 0 || from >= order.length || to < 0 || to >= order.length) return order;
	const next = [...order];
	const [item] = next.splice(from, 1);
	next.splice(to, 0, item);
	return next;
}

/** Switch between one 4-piece set and 2 + 2; the first chosen set is kept. */
export function setsFor(mode: 4 | 2, sets: ArtifactTarget['sets']): ArtifactTarget['sets'] {
	return sets.length ? [{ set_id: sets[0].set_id, pieces: mode }] : [];
}

/** Put `setId` in picker `index` (null clears it). The same set twice is ignored. */
export function setSlot(sets: ArtifactTarget['sets'], index: number, setId: number | null, mode: 4 | 2): ArtifactTarget['sets'] {
	const ids = sets.map((s) => s.set_id);
	if (setId !== null && ids.some((id, i) => id === setId && i !== index)) return sets;
	if (setId === null) ids.splice(index, 1);
	else ids[index] = setId;
	return ids.filter((id) => id !== undefined).map((set_id) => ({ set_id, pieces: mode }));
}

export function sourceLabel(opt: ArtifactSetOption | undefined): string {
	if (!opt) return 'Drop source unknown';
	return opt.domain ? opt.domain.entrance : 'Not from a domain';
}
