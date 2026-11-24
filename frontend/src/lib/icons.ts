/** Original single-colour icons (24×24), drawn for Ad Astra in the spirit of the game's menu. Not game art. */
export interface IconPath { d: string; evenodd?: boolean }

export const ICON_NAMES = [
	'dashboard', 'characters', 'teams', 'inventory', 'map', 'events', 'wishes', 'sync', 'profile', 'settings', 'external',
	'commission', 'expedition', 'friendship', 'waypoint', 'domain', 'abyss', 'chest', 'oculus', 'teapot', 'boss'
] as const;
export type IconName = (typeof ICON_NAMES)[number];

export const ICONS: Record<IconName, IconPath[]> = {
	dashboard: [{ d: 'M3 3h8v10H3zM13 3h8v6h-8zM13 11h8v10h-8zM3 15h8v6H3z' }],
	characters: [
		{ d: 'M7.5 7.5a4.5 4.5 0 1 0 9 0a4.5 4.5 0 1 0-9 0z' },
		{ d: 'M3 22c0-5 4-8.5 9-8.5s9 3.5 9 8.5z' }
	],
	teams: [
		{ d: 'M4 8a3 3 0 1 0 6 0a3 3 0 1 0-6 0z' },
		{ d: 'M14 8a3 3 0 1 0 6 0a3 3 0 1 0-6 0z' },
		{ d: 'M8.6 6a3.4 3.4 0 1 0 6.8 0a3.4 3.4 0 1 0-6.8 0z' },
		{ d: 'M1 20c0-3.5 2.6-6 6-6 1.2 0 2.3.3 3.2.9A7 7 0 0 0 7.5 20z' },
		{ d: 'M23 20c0-3.5-2.6-6-6-6-1.2 0-2.3.3-3.2.9a7 7 0 0 1 2.7 5.1z' },
		{ d: 'M5.5 21c0-4 2.9-7 6.5-7s6.5 3 6.5 7z' }
	],
	inventory: [
		{ d: 'M9 2h6a2 2 0 0 1 2 2v2h-2V4H9v2H7V4a2 2 0 0 1 2-2z' },
		{ d: 'M5 6h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2zm3 7v2h8v-2z', evenodd: true }
	],
	map: [{ d: 'M2 5l6-2 8 3 6-2v16l-6 2-8-3-6 2zm7 0v13l6 2.2V7.2z', evenodd: true }],
	events: [{ d: 'M7 1h2v3h6V1h2v3h3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h3zM4 9v11h16V9zm2 2h4v4H6z', evenodd: true }],
	wishes: [
		{ d: 'M12 1c1 6 3 9 9.5 11C15 14 13 17 12 23c-1-6-3-9-9.5-11C9 10 11 7 12 1z' },
		{ d: 'M18.4 4a1.6 1.6 0 1 0 3.2 0a1.6 1.6 0 1 0-3.2 0z' },
		{ d: 'M3.3 19.5a1.2 1.2 0 1 0 2.4 0a1.2 1.2 0 1 0-2.4 0z' }
	],
	sync: [{ d: 'M12 3a9 9 0 0 1 8.5 6H23l-4 5-4-5h2.3A6 6 0 0 0 6.2 9.5L3.6 8A9 9 0 0 1 12 3zM12 21a9 9 0 0 1-8.5-6H1l4-5 4 5H6.7a6 6 0 0 0 11.1.5l2.6 1.5A9 9 0 0 1 12 21z' }],
	profile: [{ d: 'M3 4h18a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zm5 3a3 3 0 1 0 0 6 3 3 0 0 0 0-6zm-4.5 10h9c0-2.5-2-4-4.5-4s-4.5 1.5-4.5 4zM14 8v2h6V8zm0 4v2h5v-2z', evenodd: true }],
	settings: [{ d: 'M10 1h4l.6 3a8 8 0 0 1 2.2 1.3l2.9-1 2 3.4-2.3 2a8 8 0 0 1 0 2.6l2.3 2-2 3.4-2.9-1A8 8 0 0 1 14.6 20l-.6 3h-4l-.6-3a8 8 0 0 1-2.2-1.3l-2.9 1-2-3.4 2.3-2a8 8 0 0 1 0-2.6l-2.3-2 2-3.4 2.9 1A8 8 0 0 1 9.4 4zm2 7a4 4 0 1 0 0 8 4 4 0 0 0 0-8z', evenodd: true }],
	commission: [{ d: 'M5 2h11l4 4v16H5zm10 1.5V7h3.5zM8 10v2h9v-2zm0 4v2h9v-2zm0 4v2h6v-2z', evenodd: true }],
	expedition: [{ d: 'M12 2a7 7 0 0 1 7 7c0 5-7 13-7 13S5 14 5 9a7 7 0 0 1 7-7zm0 4a3 3 0 1 0 0 6 3 3 0 0 0 0-6z', evenodd: true }],
	external: [{ d: 'M14 3h7v7h-2V6.4l-8.3 8.3-1.4-1.4L17.6 5H14zM5 5h6v2H5v12h12v-6h2v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z' }],
	friendship: [{ d: 'M12 21l-1.5-1.3C5 15 2 12.2 2 8.5 2 5.4 4.4 3 7.5 3c1.7 0 3.4.8 4.5 2.1C13.1 3.8 14.8 3 16.5 3 19.6 3 22 5.4 22 8.5c0 3.7-3 6.5-8.5 11.2z' }],
	waypoint: [{ d: 'M12 1l5 8-5 14-5-14zm0 4.5L9.8 9 12 15l2.2-6z', evenodd: true }],
	domain: [{ d: 'M3 21V9l9-6 9 6v12h-6v-6a3 3 0 0 0-6 0v6z' }],
	abyss: [{ d: 'M12 2l2.6 6.9L22 9.3l-5.6 4.6L18.2 21 12 17.3 5.8 21l1.8-7.1L2 9.3l7.4-.4z' }],
	chest: [{ d: 'M4 8a4 4 0 0 1 4-4h8a4 4 0 0 1 4 4v2H4zM4 12h7v2h2v-2h7v8H4z' }],
	oculus: [{ d: 'M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18zm0 4l1.5 3.5L17 12l-3.5 1.5L12 17l-1.5-3.5L7 12l3.5-1.5z', evenodd: true }],
	teapot: [{ d: 'M8 4h8v2h-1v2h3a3 3 0 0 1 3 3v1a3 3 0 0 1-3 3h-.4A7 7 0 0 1 5 15H3l2-5V8h4V6H8zm11 6v3a1 1 0 0 0 1-1v-1a1 1 0 0 0-1-1z', evenodd: true }],
	boss: [{ d: 'M12 2c4.4 0 8 3.4 8 7.6 0 2.6-1.3 4.8-3.3 6.2V20H7.3v-4.2C5.3 14.4 4 12.2 4 9.6 4 5.4 7.6 2 12 2zm-3 7a2 2 0 1 0 0 4 2 2 0 0 0 0-4zm6 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4z', evenodd: true }]
};
