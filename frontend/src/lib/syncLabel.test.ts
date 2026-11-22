import { describe, expect, it } from 'vitest';
import { skippedNote, syncBadge } from './syncLabel';

describe('skippedNote', () => {
	it('names the hourly throttle skip', () => {
		expect(skippedNote({ ok: true, skipped: 'fresh' })).toBe('skipped: fresh');
	});
	it('lists characters the gaps part could not plan by name', () => {
		expect(skippedNote({ ok: true, count: 3, skipped: ['Traveler'] })).toBe('not planned: Traveler');
		expect(skippedNote({ ok: true, skipped: ['Traveler', 'Aloy'] })).toBe('not planned: Traveler, Aloy');
	});
	it('says nothing when nothing was skipped', () => {
		expect(skippedNote({ ok: true })).toBe('');
		expect(skippedNote({ ok: true, skipped: [] })).toBe('');	});
});

describe('syncBadge', () => {
	const now = Date.parse('2026-11-22T12:00:00Z');
	const run = (parts: Record<string, { ok: boolean; error?: string }>, finished = '2026-11-22T11:57:00Z') =>
		({ id: 1, trigger: 'manual', started_at: finished, finished_at: finished, parts });

	it('shows nothing yet before the first status arrives', () => {
		expect(syncBadge(null, now)).toEqual({ tone: 'none', short: '…', running: false });
	});
	it('says Never when nothing has synced', () => {
		expect(syncBadge({ running: false, runs: [] } as never, now)).toEqual({ tone: 'none', short: 'Never', running: false });
	});
	it('is ok with a short age when every part succeeded', () => {
		expect(syncBadge({ running: false, runs: [run({ roster: { ok: true } })] } as never, now))
			.toEqual({ tone: 'ok', short: '3m ago', running: false });
	});
	it('warns with a count when a part failed', () => {
		expect(syncBadge({ running: false, runs: [run({ roster: { ok: true }, notes: { ok: false, error: 'x' } })] } as never, now))
			.toEqual({ tone: 'warn', short: '1 failed', running: false });
	});
	it('says Syncing while running and keeps the last tone', () => {
		expect(syncBadge({ running: true, runs: [run({ roster: { ok: true } })] } as never, now))
			.toEqual({ tone: 'ok', short: 'Syncing…', running: true });
	});
	it('uses hours and days for older syncs', () => {
		expect(syncBadge({ running: false, runs: [run({ roster: { ok: true } }, '2026-11-22T09:00:00Z')] } as never, now).short).toBe('3h ago');
		expect(syncBadge({ running: false, runs: [run({ roster: { ok: true } }, '2026-11-20T12:00:00Z')] } as never, now).short).toBe('2d ago');
		expect(syncBadge({ running: false, runs: [run({ roster: { ok: true } }, '2026-11-22T11:59:40Z')] } as never, now).short).toBe('now');
	});
});
