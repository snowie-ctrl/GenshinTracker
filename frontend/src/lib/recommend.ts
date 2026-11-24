import { emptyTarget, MAIN_SLOTS } from './artifacts';
import type { ArtifactTarget, StatRecommendation } from './types';

/** The target with HoYoLAB's main stats and substats; sets are kept. */
export function applyRecommendation(target: ArtifactTarget | null, rec: StatRecommendation): ArtifactTarget {
	const base = target ?? emptyTarget();
	return {
		sets: base.sets.map((s) => ({ ...s })),
		main: { sands: [...rec.main.sands], goblet: [...rec.main.goblet], circlet: [...rec.main.circlet] },
		subs: [...rec.subs]
	};
}

const sameSet = (a: string[], b: string[]) => a.length === b.length && a.every((k) => b.includes(k));

/** Main stats compared per slot ignoring order; substats compared in order. */
export function matchesRecommendation(target: ArtifactTarget | null, rec: StatRecommendation): boolean {
	if (!target) return false;
	return MAIN_SLOTS.every((slot) => sameSet(target.main[slot] ?? [], rec.main[slot] ?? []))
		&& target.subs.length === rec.subs.length && target.subs.every((k, i) => rec.subs[i] === k);
}
