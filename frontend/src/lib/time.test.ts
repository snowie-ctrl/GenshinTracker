import { describe, expect, it } from 'vitest';
import { formatDuration, timeAgo } from './time';
import { lastFinished, syncLabel } from './syncLabel';
import type { SyncStatus } from './types';

describe('formatDuration', () => {
	it('formats minutes and hours', () => {
		expect(formatDuration(0)).toBe('now');
		expect(formatDuration(-5)).toBe('now');
		expect(formatDuration(59_000)).toBe('1m');
		expect(formatDuration(3_600_000 + 5 * 60_000)).toBe('1h 5m');
	});
});

describe('timeAgo', () => {
	const now = Date.parse('2026-11-19T12:00:00Z');
	it('formats relative times', () => {
		expect(timeAgo('2026-11-19T11:59:30Z', now)).toBe('just now');
		expect(timeAgo('2026-11-19T11:57:00Z', now)).toBe('3 min ago');
		expect(timeAgo('2026-11-19T09:00:00Z', now)).toBe('3 h ago');
		expect(timeAgo('2026-11-17T12:00:00Z', now)).toBe('2 d ago');
	});
});

describe('syncLabel', () => {
	const now = Date.parse('2026-11-19T12:00:00Z');
	const run = (parts: SyncStatus['runs'][0]['parts'], finished: string | null = '2026-11-19T11:57:00Z') => ({
		id: 1, trigger: 'auto', started_at: '2026-11-19T11:56:50Z', finished_at: finished, parts
	});
	it('covers each state', () => {
		expect(syncLabel(null, now)).toBe('…');
		expect(syncLabel({ running: true, runs: [] }, now)).toBe('Syncing…');
		expect(syncLabel({ running: false, runs: [] }, now)).toBe('Not synced yet');
		expect(syncLabel({ running: false, runs: [run({ roster: { ok: true } })] }, now)).toBe('Synced 3 min ago');
		expect(
			syncLabel({ running: false, runs: [run({ roster: { ok: true }, notes: { ok: false, error: 'x' } })] }, now)
		).toBe('⚠ 1 part failed');
	});
	it('ignores gaps-only runs', () => {
		const gapsRun = { ...run({ gaps: { ok: false, error: 'x' } }, '2026-11-19T11:59:00Z'), id: 2, trigger: 'gaps' };
		const full = run({ roster: { ok: true } });
		expect(syncLabel({ running: false, runs: [gapsRun, full] }, now)).toBe('Synced 3 min ago');
		expect(lastFinished({ running: false, runs: [gapsRun, full] })).toBe(full);
		expect(syncLabel({ running: false, runs: [gapsRun] }, now)).toBe('Not synced yet');
	});
});
