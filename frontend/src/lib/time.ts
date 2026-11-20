export function formatDuration(ms: number): string {
	if (ms <= 0) return 'now';
	const totalMinutes = Math.ceil(ms / 60_000);
	const h = Math.floor(totalMinutes / 60);
	const m = totalMinutes % 60;
	return h ? `${h}h ${m}m` : `${m}m`;
}

export function timeAgo(iso: string, now: number): string {
	const ms = now - Date.parse(iso);
	if (ms < 60_000) return 'just now';
	const m = Math.floor(ms / 60_000);
	if (m < 60) return `${m} min ago`;
	const h = Math.floor(m / 60);
	if (h < 24) return `${h} h ago`;
	return `${Math.floor(h / 24)} d ago`;
}
