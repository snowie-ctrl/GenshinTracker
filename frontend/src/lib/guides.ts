/** Third-party community build guides (Genshin Impact Helper Team). Linked only, never fetched. */
export const COMMUNITY_GUIDE_BASE = 'https://genshin-impact-helper-team.github.io/genshin-builds/en/';

// Our slug -> theirs, where they differ (checked against their full character list on 2026-11-24).
const EXCEPTIONS: Record<string, string> = { 'raiden-shogun': 'shogun-raiden' };

export function communityGuideUrl(slug: string): string {
	return COMMUNITY_GUIDE_BASE + (EXCEPTIONS[slug] ?? slug);
}
