/** Element and rarity look, shared by every page that shows them. Icons load at runtime through /api/img. */
export const ELEMENT_STYLE: Record<string, { color: string; icon: string }> = {
	Pyro: { color: 'var(--pyro)', icon: 'UI_Buff_Element_Fire' },
	Hydro: { color: 'var(--hydro)', icon: 'UI_Buff_Element_Water' },
	Anemo: { color: 'var(--anemo)', icon: 'UI_Buff_Element_Wind' },
	Electro: { color: 'var(--electro)', icon: 'UI_Buff_Element_Electric' },
	Dendro: { color: 'var(--dendro)', icon: 'UI_Buff_Element_Grass' },
	Cryo: { color: 'var(--cryo)', icon: 'UI_Buff_Element_Ice' },
	Geo: { color: 'var(--geo)', icon: 'UI_Buff_Element_Rock' }
};

export function elementStyle(name: string | null | undefined): { color: string; icon: string | null } {
	return (name && ELEMENT_STYLE[name]) || { color: 'var(--pill-neutral)', icon: null };
}

export const RARITY_STYLE: Record<number, { color: string; ink: string }> = {
	5: { color: 'var(--rarity-5)', ink: '#17130b' },
	4: { color: 'var(--rarity-4)', ink: '#ffffff' }
};
