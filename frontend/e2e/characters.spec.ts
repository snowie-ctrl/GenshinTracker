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
