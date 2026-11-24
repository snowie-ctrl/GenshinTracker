import { describe, expect, it } from 'vitest';
import { COMMUNITY_GUIDE_BASE, communityGuideUrl } from './guides';

describe('communityGuideUrl', () => {
	it('uses our slug', () => {
		expect(communityGuideUrl('bennett')).toBe(`${COMMUNITY_GUIDE_BASE}bennett`);
		expect(communityGuideUrl('hu-tao')).toBe(`${COMMUNITY_GUIDE_BASE}hu-tao`);
	});
	it('maps the exceptions', () => {
		expect(communityGuideUrl('raiden-shogun')).toBe(`${COMMUNITY_GUIDE_BASE}shogun-raiden`);
	});
	it('keeps Traveler element slugs', () => {
		expect(communityGuideUrl('anemo-traveler')).toBe(`${COMMUNITY_GUIDE_BASE}anemo-traveler`);
	});
	it('points at the English site', () => {
		expect(COMMUNITY_GUIDE_BASE).toBe('https://genshin-impact-helper-team.github.io/genshin-builds/en/');
	});
});
