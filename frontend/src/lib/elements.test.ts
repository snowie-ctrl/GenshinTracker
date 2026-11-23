import { describe, expect, it } from 'vitest';
import { ELEMENTS } from './status';
import { ELEMENT_HEX, ELEMENT_STYLE, RARITY_STYLE, elementHex, elementStyle } from './elements';

describe('elements', () => {
	it('styles every element with a colour token and its icon', () => {
		for (const el of ELEMENTS) {
			expect(ELEMENT_STYLE[el].color).toBe(`var(--${el.toLowerCase()})`);
			expect(ELEMENT_STYLE[el].icon).toMatch(/^UI_Buff_Element_/);
		}
		expect(ELEMENT_STYLE.Electro.icon).toBe('UI_Buff_Element_Electric');
		expect(ELEMENT_STYLE.Cryo.icon).toBe('UI_Buff_Element_Ice');
	});
	it('falls back to neutral for unknown or missing elements', () => {
		expect(elementStyle('Physical')).toEqual({ color: 'var(--pill-neutral)', icon: null });
		expect(elementStyle(null)).toEqual({ color: 'var(--pill-neutral)', icon: null });
	});
	it('gives 5★ gold with dark text and 4★ purple with white text', () => {
		expect(RARITY_STYLE[5]).toEqual({ color: 'var(--rarity-5)', ink: '#17130b' });
		expect(RARITY_STYLE[4]).toEqual({ color: 'var(--rarity-4)', ink: '#ffffff' });
	});
});

describe('elementHex', () => {
	it('maps every element to a hex colour and unknowns to null', () => {
		expect(Object.keys(ELEMENT_HEX).sort()).toEqual(['Anemo', 'Cryo', 'Dendro', 'Electro', 'Geo', 'Hydro', 'Pyro']);
		expect(elementHex('Hydro')).toBe('#4cc2f1');
		expect(elementHex(null)).toBeNull();
		expect(elementHex('Light')).toBeNull();
	});
});
