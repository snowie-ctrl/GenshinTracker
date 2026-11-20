import { timeAgo } from './time';
import type { SyncRun, SyncStatus } from './types';

export function lastFinished(s: SyncStatus | null): SyncRun | null {
	return s?.runs.find((r) => r.finished_at) ?? null;
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
