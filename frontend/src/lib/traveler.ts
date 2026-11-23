import type { TravelerInfo } from './types';

export function clampTalent(n: number): number {
	return Number.isFinite(n) ? Math.min(10, Math.max(1, Math.floor(n))) : 1;
}
export function clampCons(n: number): number {
	return Number.isFinite(n) ? Math.min(6, Math.max(0, Math.floor(n))) : 0;
}
export const editable = (t: TravelerInfo) => !t.current;
export const unlockLocked = (t: TravelerInfo) => t.seen;
