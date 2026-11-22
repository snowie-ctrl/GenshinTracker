import { timeAgo } from './time';
import type { SyncPart, SyncRun, SyncStatus } from './types';

/** Last finished full sync: gaps-only recalculations say nothing about roster/details/notes. */
export function lastFinished(s: SyncStatus | null): SyncRun | null {
	return s?.runs.find((r) => r.finished_at && r.trigger !== 'gaps') ?? null;
}

export function failedParts(run: SyncRun): string[] {
	return Object.entries(run.parts).filter(([, p]) => !p.ok).map(([name]) => name);
}

export function syncLabel(s: SyncStatus | null, now: number): string {
	if (!s) return '…';
	if (s.running) return 'Syncing…';
	const last = lastFinished(s);
	if (!last) return 'Not synced yet';
	const failed = failedParts(last);
	if (failed.length) return `⚠ ${failed.length} part${failed.length > 1 ? 's' : ''} failed`;
	return `Synced ${timeAgo(last.finished_at!, now)}`;
}

/** 'fresh' is the hourly throttle skip; a list names characters the gaps part could not plan. */
export function skippedNote(part: SyncPart): string {
	if (part.skipped === 'fresh') return 'skipped: fresh';
	if (Array.isArray(part.skipped) && part.skipped.length) return `not planned: ${part.skipped.join(', ')}`;
	return '';
}

export type SyncTone = 'ok' | 'warn' | 'none';

function shortAgo(iso: string, now: number): string {
	const m = Math.floor((now - Date.parse(iso)) / 60_000);
	if (m < 1) return 'now';
	if (m < 60) return `${m}m ago`;
	const h = Math.floor(m / 60);
	if (h < 24) return `${h}h ago`;
	return `${Math.floor(h / 24)}d ago`;
}

/** Sidebar sync item: a status dot tone and a label short enough for 76px. */
export function syncBadge(s: SyncStatus | null, now: number): { tone: SyncTone; short: string; running: boolean } {
	if (!s) return { tone: 'none', short: '…', running: false };
	const last = lastFinished(s);
	const failed = last ? failedParts(last).length : 0;
	const tone: SyncTone = !last ? 'none' : failed ? 'warn' : 'ok';
	if (s.running) return { tone, short: 'Syncing…', running: true };
	if (!last) return { tone, short: 'Never', running: false };
	return { tone, short: failed ? `${failed} failed` : shortAgo(last.finished_at!, now), running: false };
}
