/** Pure maths for the Events timeline: a day axis, bar positions (0..1 of the axis) and lane packing. */
export const DAY = 86_400_000;
export const BACK_DAYS = 21;
export const MIN_AHEAD_DAYS = 14;
export const MAX_AHEAD_DAYS = 60;

export interface Axis { start: number; end: number; days: number }
export interface Placed<T> { row: T; lane: number; left: number; width: number; clampedEnd: boolean; from: number; to: number }

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export function dayStart(ms: number): number {
	const d = new Date(ms);
	return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

function ms(s: string | null): number | null {
	if (!s) return null;
	const v = Date.parse(s);
	return Number.isNaN(v) ? null : v;
}

export function buildAxis(rows: { start: string | null; end: string | null }[], now: number): Axis {
	const today = dayStart(now);
	const start = today - BACK_DAYS * DAY;
	const min = today + (MIN_AHEAD_DAYS + 1) * DAY;
	const max = today + (MAX_AHEAD_DAYS + 1) * DAY;
	let end = min;
	for (const r of rows) {
		const e = ms(r.end);
		if (e !== null) end = Math.max(end, dayStart(e) + DAY);
	}
	end = Math.min(end, max);
	return { start, end, days: Math.round((end - start) / DAY) };
}

export function placeBars<T extends { start: string | null; end: string | null }>(rows: T[], axis: Axis): Placed<T>[] {
	const span = axis.end - axis.start;
	const items = rows
		.map((row) => {
			const e = ms(row.end);
			if (e === null || e <= axis.start) return null;
			const s = Math.max(ms(row.start) ?? axis.start, axis.start);
			const clampedEnd = e > axis.end;
			const to = Math.min(e, axis.end);
			return { row, from: s, to, clampedEnd };
		})
		.filter((x): x is { row: T; from: number; to: number; clampedEnd: boolean } => x !== null && x.to > x.from)
		.sort((a, b) => a.from - b.from || a.to - b.to);
	const laneEnds: number[] = [];
	return items.map((it) => {
		let lane = laneEnds.findIndex((end) => end <= it.from);
		if (lane === -1) {
			lane = laneEnds.length;
			laneEnds.push(it.to);
		} else laneEnds[lane] = it.to;
		return { ...it, lane, left: (it.from - axis.start) / span, width: (it.to - it.from) / span };
	});
}

export function todayOffset(axis: Axis, now: number): number {
	return Math.min(1, Math.max(0, (now - axis.start) / (axis.end - axis.start)));
}

export function dayTicks(axis: Axis): { ms: number; label: string; monthStart: boolean }[] {
	const out: { ms: number; label: string; monthStart: boolean }[] = [];
	for (let i = 0; i < axis.days; i++) {
		const d = new Date(axis.start + i * DAY + DAY / 2);
		const at = dayStart(d.getTime());
		const monthStart = d.getDate() === 1;
		out.push({ ms: at, label: monthStart ? MONTHS[d.getMonth()] : String(d.getDate()), monthStart });
	}
	return out;
}
