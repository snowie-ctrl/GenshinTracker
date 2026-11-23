import type { Kit, ScaleRow, TalentRole } from './types';

export interface Column { key: 'now' | 'target' | 'max'; label: string; level: number }
export interface LevelPoint { base: number; constellation: number }

export function raisedBy(kit: Kit | null, role: TalentRole): number | null {
	return kit?.constellations.find((c) => c.raises === role)?.index ?? null;
}

export function boost(kit: Kit | null, role: TalentRole, constellation: number): number {
	const c = raisedBy(kit, role);
	return c !== null && constellation >= c ? 3 : 0;
}

export function effectiveLevel(base: number, kit: Kit | null, role: TalentRole, constellation: number): number {
	return base + boost(kit, role, constellation);
}

export function maxLevel(kit: Kit | null, role: TalentRole, owned: number, target: number): number {
	return 10 + boost(kit, role, Math.max(owned, target));
}

export function scalingColumns(kit: Kit | null, role: TalentRole, now: LevelPoint | null,
	target: LevelPoint | null): Column[] {
	const cols: Column[] = [];
	if (now) {
		const level = effectiveLevel(now.base, kit, role, now.constellation);
		cols.push({ key: 'now', label: `Lv ${level} (now)`, level });
	}
	if (target) {
		// A target at or below what is owned is already reached: show the owned level, never a lower one.
		const base = now ? Math.max(now.base, target.base) : target.base;
		const level = effectiveLevel(base, kit, role, now ? Math.max(now.constellation, target.constellation) : target.constellation);
		const reached = now !== null && target.base <= now.base;
		cols.push({ key: 'target', label: `Lv ${level} (${reached ? 'reached' : 'target'})`, level });
	}
	const max = maxLevel(kit, role, now?.constellation ?? 0, target?.constellation ?? 0);
	cols.push({ key: 'max', label: `Lv ${max} (max)`, level: max });
	return cols;
}

export function valueAt(row: ScaleRow, level: number): string {
	return row.values[level - 1] || '—';
}

/** A stored wish target of null (rows from before sub-project 5) means "same as current". */
export function buildValue(stored: number | null | undefined, current: number): number {
	return stored ?? current;
}

export function isReached(current: number, target: number): boolean {
	return target <= current;
}

const COLOR = /^#[0-9A-Fa-f]{6}$/;

/** Only a plain #RRGGBB colour is ever put into a style attribute. */
export function safeColor(color: string | null | undefined): string | undefined {
	return color && COLOR.test(color) ? color : undefined;
}
