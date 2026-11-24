import type { TileView } from './materials';
import type { BuildMaterial, Expedition, PityLine, Reward } from './types';

export function greeting(hour: number, name: string): string {
	const part = hour >= 5 && hour < 12 ? 'Good morning' : hour >= 12 && hour < 18 ? 'Good afternoon' : 'Good evening';
	return `${part}, ${name.trim() || 'Traveler'}`;
}

export const DAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] as const;
export interface DayButton { day: number; label: string; viewed: boolean; today: boolean }

export function dayButtons(viewed: number, today: number): DayButton[] {
	return DAY_LABELS.map((label, day) => ({ day, label, viewed: day === viewed, today: day === today }));
}

export function moveItem<T>(list: T[], from: number, to: number): T[] {
	const out = list.slice();
	if (from === to || from < 0 || to < 0 || from >= list.length || to >= list.length) return out;
	const [item] = out.splice(from, 1);
	out.splice(to, 0, item);
	return out;
}

export function covered(m: BuildMaterial): boolean {
	return m.have + m.craft >= m.need;
}

export function buildTileView(m: BuildMaterial): TileView {
	const left = Math.max(0, m.need - m.have - m.craft);
	return {
		main: `${m.have}/${m.need}`,
		badge: left > 0 ? `−${left}` : null,
		craft: null,
		hint: m.craft > 0 ? `+${m.craft} craft` : null,
		tone: left === 0 ? 'met' : 'short'
	};
}

export function topReward(rewards: Reward[]): Reward | null {
	return rewards.reduce<Reward | null>(
		(best, r) => (!best || r.rarity > best.rarity || (r.rarity === best.rarity && r.count > best.count) ? r : best),
		null
	);
}

export function expeditionsReady(exps: Expedition[], now: number): number {
	return exps.filter((e) => e.finished || Date.parse(e.return_at) <= now).length;
}

export function bannerPity(line: PityLine | null): string | null {
	if (!line) return null;
	const state = line.next_state === 'guaranteed' ? ' · guaranteed'
		: line.next_state === '50/50' || line.next_state === '75/25' ? ` · ${line.next_state}` : '';
	return `Pity ${line.pity5}/${line.hard}${state}`;
}
