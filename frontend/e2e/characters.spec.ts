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
	await expect(page.getByLabel('Target level')).toBeVisible();
	await expect(page.getByLabel('Target normal attack')).toBeVisible();
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

test('Traveler element card: unlock another element', async ({ page }) => {
	await page.goto('/characters/cryo-traveler');
	await expect(page.getByRole('heading', { name: 'Cryo Traveler' })).toBeVisible();
	await expect(page.getByText('From HoYoLAB: current element')).toBeVisible();
	await page.goto('/characters/anemo-traveler');
	const toggle = page.getByRole('checkbox', { name: 'Unlocked' });
	await expect(toggle).not.toBeChecked();
	await toggle.check();
	await expect(page.getByRole('heading', { name: 'Current' })).toBeVisible();
	await expect(page.getByText('Lv 90 · C0')).toBeVisible();
});

test('Traveler element card: out-of-range talent snaps back to the saved value', async ({ page }) => {
	await page.goto('/characters/anemo-traveler');
	await page.getByRole('checkbox', { name: 'Unlocked' }).check();
	await expect(page.getByRole('heading', { name: 'Current' })).toBeVisible();
	const normal = page.getByRole('spinbutton', { name: 'Normal attack' });
	await normal.fill('15');
	await normal.blur();
	await expect(normal).toHaveValue('10');
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
