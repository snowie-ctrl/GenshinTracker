import { expect, test } from '@playwright/test';

test('setting a character to Build moves it into Actively building', async ({ page }) => {
	await page.goto('/characters');

	const obtained = page.getByTestId('section-obtained');
	const card = obtained.getByTestId('card-xiangling');
	await expect(card).toBeVisible();
	await card.hover();
	await card.getByRole('button', { name: 'Build' }).click();

	const building = page.getByTestId('section-building');
	const moved = building.getByTestId('card-xiangling');
	await expect(moved).toBeVisible();
	await expect(moved.getByRole('progressbar')).toBeVisible();
	await expect(obtained.getByTestId('card-xiangling')).toHaveCount(0);

	await moved.getByRole('link', { name: 'Xiangling' }).click();
	await expect(page).toHaveURL(/\/characters\/xiangling$/);
	await expect(page.getByTestId('banner').getByRole('heading', { name: 'Xiangling' })).toBeVisible();
	await page.getByTestId('banner').getByRole('button', { name: 'None' }).click(); // restore
	await expect(page.getByTestId('banner').getByRole('button', { name: 'None' })).toHaveAttribute('aria-pressed', 'true');
});

test('unobtained section starts collapsed and expands', async ({ page }) => {
	await page.goto('/characters');
	const section = page.getByTestId('section-unobtained');
	await expect(section.getByTestId('card-xingqiu')).toHaveCount(0);
	await section.getByRole('button', { name: /Unobtained/ }).click();
	await expect(section.getByTestId('card-xingqiu')).toBeVisible();
});

test('element pills filter and report their state', async ({ page }) => {
	await page.goto('/characters');
	const pyro = page.getByRole('button', { name: 'Pyro', exact: true });
	await expect(pyro).toHaveAttribute('aria-pressed', 'false');
	await pyro.click();
	await expect(pyro).toHaveAttribute('aria-pressed', 'true');
	// dev seed: Xiangling (Pyro, obtained), Bennett (Pyro, building), Nahida (Dendro, obtained), Furina (Hydro, building)
	await expect(page.getByTestId('card-xiangling')).toBeVisible();
	await expect(page.getByTestId('card-bennett')).toBeVisible();
	await expect(page.getByTestId('card-nahida')).toHaveCount(0);
	await expect(page.getByTestId('card-furina')).toHaveCount(0);
	await pyro.click();
	await expect(pyro).toHaveAttribute('aria-pressed', 'false');
	await expect(page.getByTestId('card-nahida')).toBeVisible();
});

test('a pill whose element icon fails to load still shows its label and filters', async ({ page }) => {
	await page.route('**/api/img/UI_Buff_Element_*', (route) => route.fulfill({ status: 404, body: '' }));
	await page.goto('/characters');
	const pyro = page.getByRole('button', { name: 'Pyro', exact: true });
	await expect(pyro).toBeVisible();
	await expect(pyro.locator('img')).toHaveCount(0);
	await pyro.click();
	await expect(page.getByTestId('card-xiangling')).toBeVisible();
});

test('banner shows the character, element tint and tabs', async ({ page }) => {
	await page.goto('/characters/furina');
	const banner = page.getByTestId('banner');
	await expect(banner.getByRole('heading', { name: 'Furina' })).toBeVisible();
	await expect(banner.getByText('Hydro')).toBeVisible();
	await expect(page.getByTestId('starfield')).toHaveAttribute('data-tint', '#4cc2f1');
	await expect(page.getByTestId('tab-current')).toHaveAttribute('aria-current', 'page');
	await expect(page.getByTestId('current-level')).toContainText('90');
	await expect(page.getByTestId('talent-skill')).toBeVisible();
	await expect(page.getByTestId('in-teams')).toBeVisible();
	await expect(page.getByTestId('tab-build')).toHaveAttribute('href', '/characters/furina/build');
	await expect(page.getByTestId('tab-guide')).toHaveAttribute('href', '/characters/furina/guide');
	await page.getByTestId('tab-build').click();
	await expect(page).toHaveURL(/\/characters\/furina\/build$/);
	await expect(page.getByTestId('tab-build')).toHaveAttribute('aria-current', 'page');
	await page.getByTestId('tab-guide').click();
	await expect(page).toHaveURL(/\/characters\/furina\/guide$/);
	await expect(page.getByTestId('tab-guide')).toHaveAttribute('aria-current', 'page');
});

test('switching character updates the banner and tint; leaving clears the tint', async ({ page }) => {
	await page.goto('/characters/furina');
	await expect(page.getByTestId('starfield')).toHaveAttribute('data-tint', '#4cc2f1');
	await page.goto('/characters/bennett');
	await expect(page.getByTestId('banner').getByRole('heading', { name: 'Bennett' })).toBeVisible();
	await expect(page.getByTestId('starfield')).toHaveAttribute('data-tint', '#ef7a4a');
	await page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Characters', exact: true }).click();
	await expect(page).toHaveURL(/\/characters$/);
	await expect(page.getByTestId('starfield')).toHaveAttribute('data-tint', '');
});

test('Traveler element card: unlock another element', async ({ page }) => {
	await page.goto('/characters/cryo-traveler');
	await expect(page.getByTestId('banner').getByRole('heading', { name: 'Cryo Traveler' })).toBeVisible();
	await expect(page.getByText('From HoYoLAB: current element')).toBeVisible();
	await page.goto('/characters/anemo-traveler');
	const toggle = page.getByRole('checkbox', { name: 'Unlocked' });
	await expect(toggle).not.toBeChecked();
	await toggle.check();
	await expect(page.getByTestId('current-level')).toContainText('90');
	await expect(page.getByTestId('current-constellation')).toContainText('C0');
	await toggle.uncheck(); // restore
	await expect(toggle).not.toBeChecked();
});

test('Traveler element card: out-of-range talent snaps back to the saved value', async ({ page }) => {
	await page.goto('/characters/anemo-traveler');
	await page.getByRole('checkbox', { name: 'Unlocked' }).check();
	await expect(page.getByTestId('current-level')).toBeVisible();
	const normal = page.getByRole('spinbutton', { name: 'Normal attack' });
	await normal.fill('15');
	await normal.blur();
	await expect(normal).toHaveValue('10');
	await page.getByRole('checkbox', { name: 'Unlocked' }).uncheck(); // restore
});

test('large tiles persist across a reload and switch back', async ({ page }) => {
	await page.goto('/characters');
	await page.getByRole('button', { name: 'Large', exact: true }).click();
	await expect(page.getByTestId('card-xiangling')).toHaveClass(/large/);
	await page.reload();
	await expect(page.getByTestId('card-xiangling')).toHaveClass(/large/);
	await page.getByRole('button', { name: 'Small', exact: true }).click();
	await expect(page.getByTestId('card-xiangling')).toHaveClass(/small/);
});

test('sort toggles reorder sections; unowned tiles are grey', async ({ page }) => {
	await page.goto('/characters');
	const rarity = page.getByRole('button', { name: 'Rarity', exact: true });
	await expect(rarity).toHaveAttribute('aria-pressed', 'true');
	await rarity.click();
	const ids = await page.getByTestId('section-obtained').locator('[data-testid^="card-"]')
		.evaluateAll((els) => els.map((e) => (e.textContent ?? '').trim()));
	expect(ids).toEqual([...ids].sort((a, b) => a.localeCompare(b)));
	await rarity.click();                                   // restore the default
	await expect(rarity).toHaveAttribute('aria-pressed', 'true');

	const section = page.getByTestId('section-unobtained');
	await section.getByRole('button', { name: /Unobtained/ }).click();
	await expect(section.getByTestId('card-xingqiu')).toHaveClass(/unowned/);
	await section.getByRole('button', { name: /Unobtained/ }).click();
});

test('Build tab edits targets and keeps them', async ({ page }) => {
	await page.goto('/characters/furina/build');
	const skill = page.getByLabel('Target elemental skill');
	const before = await skill.inputValue();
	await skill.selectOption('10');
	await page.getByLabel('Target constellation').selectOption('6');
	await page.reload();
	await expect(page.getByLabel('Target elemental skill')).toHaveValue('10');
	await expect(page.getByLabel('Target constellation')).toHaveValue('6');
	await expect(page.getByTestId('build-artifacts')).toContainText('Substat priority');
	await expect(page.getByTestId('build-suggestions-slot')).toContainText('sub-project 9');
	await page.getByLabel('Target elemental skill').selectOption(before);
	await page.getByLabel('Target constellation').selectOption('1');
	await expect(page.getByLabel('Target elemental skill')).toHaveValue(before);
});

test('Build tab marks a target at or below current as reached', async ({ page }) => {
	const original = (await (await page.request.get('/api/characters/furina')).json()).targets;
	try {
		await page.request.put('/api/characters/10000089/goal', { data: { targets: { ...original, skill: 8 } } });
		await page.goto('/characters/furina/build');
		await expect(page.getByTestId('reached-skill')).toBeVisible();
	} finally {
		await page.request.put('/api/characters/10000089/goal', { data: { targets: original } });
	}
});

test('Build tab on a non-Build character offers Set to Build', async ({ page }) => {
	await page.goto('/characters/nahida/build');
	await expect(page.getByLabel('Target level')).toBeDisabled();
	await page.getByTestId('set-build').click();
	await expect(page.getByLabel('Target level')).toBeEnabled();
	await expect(page.getByLabel('Target elemental skill')).toHaveValue('9');
	await page.getByTestId('banner').getByRole('button', { name: 'None' }).click();
	await expect(page.getByLabel('Target level')).toBeDisabled();
});

test('Guide shows talents with numbers, passives and constellations', async ({ page }) => {
	await page.goto('/characters/furina/guide');
	await expect(page.getByTestId('guide-howto-slot')).toContainText('sub-project 9');
	const talents = page.getByTestId('guide-talents');
	await expect(talents.getByText('Furina Skill')).toBeVisible();
	await expect(talents.getByRole('columnheader', { name: /\(now\)/ }).first()).toBeVisible();
	await expect(talents.getByRole('columnheader', { name: /\((target|reached)\)/ }).first()).toBeVisible();
	await expect(talents.getByText('demo DMG')).toBeVisible();
	await expect(page.getByText('Furina Passive 1')).toBeVisible();
	await expect(page.getByTestId('guide-constellations').getByText('Furina C6')).toBeVisible();
	await page.goto('/characters/bennett/guide');
	await expect(page.getByTestId('guide-talents').getByText('Bennett Skill')).toBeVisible();
});

test('Guide shows a notice when the kit is unavailable', async ({ page }) => {
	await page.route('**/api/characters/furina/kit', (route) =>
		route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ state: 'unavailable', kit: null }) }));
	await page.goto('/characters/furina/guide');
	await expect(page.getByTestId('kit-unavailable')).toBeVisible();
	await expect(page.getByTestId('kit-unavailable').getByRole('button', { name: 'Retry' })).toBeVisible();
	await page.goto('/characters/furina');
	await expect(page.getByTestId('talent-skill')).toBeVisible();
});

test('Guide tolerates duplicate talent names and scaling labels', async ({ page }) => {
	const seg = (text: string) => [[{ text, color: null, italic: false }]];
	const row = (v: string) => ({ label: 'Dup DMG', values: Array(15).fill(v) });
	const talent = { name: 'Twin Skill', icon: null, role: 'skill', cooldown: null, cost: null, scaling: [row('1%'), row('2%')] };
	const kit = {
		talents: [{ ...talent, description: seg('first body') }, { ...talent, description: seg('second body') }],
		passives: [{ name: 'Twin Passive', icon: null, description: seg('p1') }, { name: 'Twin Passive', icon: null, description: seg('p2') }],
		constellations: []
	};
	await page.route('**/api/characters/furina/kit', (route) =>
		route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ state: 'fresh', kit }) }));
	await page.goto('/characters/furina/guide');
	const talents = page.getByTestId('guide-talents');
	await expect(talents.getByText('first body')).toBeVisible();
	await expect(talents.getByText('second body')).toBeVisible();
	await expect(talents.getByRole('cell', { name: 'Dup DMG' })).toHaveCount(4);
	await expect(page.getByText('p1')).toBeVisible();
	await expect(page.getByText('p2')).toBeVisible();
});
