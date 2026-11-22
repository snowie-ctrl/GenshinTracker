import type { EventRow, EventsLeft } from './types';

export function timeLeft(iso: string | null, now: number): string {
	if (!iso) return '—';
	const ms = Date.parse(iso) - now;
	if (ms <= 0) return 'ended';
	const mins = Math.floor(ms / 60000);
	const d = Math.floor(mins / 1440);
	const h = Math.floor((mins % 1440) / 60);
	const m = mins % 60;
	if (d > 0) return `${d}d ${h}h`;
	if (h > 0) return `${h}h ${m}m`;
	return `${m}m`;
}

export function sortEvents(rows: EventRow[]): EventRow[] {
	const end = (r: EventRow) => (r.end ? Date.parse(r.end) : Number.MAX_SAFE_INTEGER);
	return [...rows].sort((a, b) => Number(a.done) - Number(b.done) || end(a) - end(b) || a.id - b.id);
}

export function leftTotals(rows: EventRow[]): EventsLeft {
	const left = rows.filter((r) => !r.done);
	return { count: left.length, primogems: left.reduce((n, r) => n + r.primogems, 0) };
}

export function primosLine(left: EventsLeft): string {
	return left.count === 0 ? 'All events done ✓' : `${left.count} left · ${left.primogems} primos unclaimed`;
}
