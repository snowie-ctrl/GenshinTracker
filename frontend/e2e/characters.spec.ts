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
