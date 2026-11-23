import type { IconName } from './icons';

export interface NavItem { label: string; href: string; icon: IconName }

export const MAIN_NAV: NavItem[] = [
	{ label: 'Dashboard', href: '/', icon: 'dashboard' },
	{ label: 'Characters', href: '/characters', icon: 'characters' },
	{ label: 'Teams', href: '/teams', icon: 'teams' },
	{ label: 'Inventory', href: '/inventory', icon: 'inventory' },
	{ label: 'Map', href: '/map', icon: 'map' },
	{ label: 'Events', href: '/events', icon: 'events' },
	{ label: 'Wishes', href: '/wishes', icon: 'wishes' }
];

export const BOTTOM_NAV: NavItem[] = [
	{ label: 'Profile', href: '/profile', icon: 'profile' },
	{ label: 'Settings', href: '/settings', icon: 'settings' }
];

export function isActive(href: string, pathname: string): boolean {
	if (href === '/') return pathname === '/';
	return pathname === href || pathname.startsWith(href + '/');
}

/** Pages that opt out of the 1600px cap and fill the window height. */
export const FLUID_ROUTES = ['/map'];

export function isFluid(pathname: string): boolean {
	return FLUID_ROUTES.some((r) => isActive(r, pathname));
}

/** Pages that use the full content width (no 1600px cap) but scroll normally. */
export const WIDE_ROUTES = ['/characters', '/teams'];

export function isWide(pathname: string): boolean {
	return WIDE_ROUTES.some((r) => pathname === r);
}
