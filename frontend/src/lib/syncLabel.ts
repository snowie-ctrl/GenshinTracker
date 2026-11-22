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
	if (Array.isArray(part.skipped) && part.skipped.length) return `skipped: ${part.skipped.join(', ')}`;
	return '';
}
