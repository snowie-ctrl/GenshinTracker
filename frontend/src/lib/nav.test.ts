import { describe, expect, it } from 'vitest';
import { BOTTOM_NAV, MAIN_NAV, isActive, isFluid } from './nav';

describe('nav', () => {
	it('lists the pages in the agreed order', () => {
		expect(MAIN_NAV.map((n) => n.label)).toEqual(['Dashboard', 'Characters', 'Teams', 'Inventory', 'Map', 'Events', 'Wishes']);
		expect(BOTTOM_NAV.map((n) => n.label)).toEqual(['Profile', 'Settings']);
	});
	it('matches the dashboard only at the root', () => {
		expect(isActive('/', '/')).toBe(true);
		expect(isActive('/', '/characters')).toBe(false);
	});
	it('matches other pages by path prefix, including nested routes', () => {
		expect(isActive('/characters', '/characters/xiangling')).toBe(true);
		expect(isActive('/teams', '/teams/3')).toBe(true);
		expect(isActive('/teams', '/characters')).toBe(false);
	});
	it('does not match a page that only shares a prefix of the name', () => {
		expect(isActive('/map', '/maps-legacy')).toBe(false);
	});
	it('treats Map as a fluid page', () => {
		expect(isFluid('/map')).toBe(true);
		expect(isFluid('/settings')).toBe(false);
	});
});

import { isWide } from './nav';
describe('isWide', () => {
	it('covers Characters and Teams but not character detail', () => {
		expect(isWide('/characters')).toBe(true);
		expect(isWide('/teams')).toBe(true);
		expect(isWide('/characters/bennett')).toBe(false);
		expect(isWide('/inventory')).toBe(false);
	});
});
