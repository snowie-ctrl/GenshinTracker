import { DEFAULT_SORT, type SortKeys } from './status';

export type TileSize = 'small' | 'large';
export interface CharacterView { size: TileSize; sort: SortKeys }
const KEY = 'aa.characterView';

export function loadCharacterView(): CharacterView {
	const fallback: CharacterView = { size: 'small', sort: { ...DEFAULT_SORT } };
	try {
		const raw = localStorage.getItem(KEY);
		if (!raw) return fallback;
		const v = JSON.parse(raw);
		const size: TileSize = v?.size === 'large' ? 'large' : 'small';
		const s = v?.sort;
		const sort = s && typeof s === 'object'
			? { az: s.az !== false, rarity: s.rarity !== false, level: s.level === true }
			: { ...DEFAULT_SORT };
		return { size, sort };
	} catch {
		return fallback;
	}
}

export function saveCharacterView(v: CharacterView): void {
	try {
		localStorage.setItem(KEY, JSON.stringify(v));
	} catch {
		/* storage blocked: keep the in-memory choice */
	}
}
