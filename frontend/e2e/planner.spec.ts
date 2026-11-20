import { expect, test } from '@playwright/test';

test('dashboard shows active domains and a weekly boss that can be ticked', async ({ page }) => {
	await page.goto('/');
	const today = page.getByTestId('farm-today');
	await expect(today.getByText('Domain of Mastery: Forsaken Rift', { exact: true })).toBeVisible();
	const boss = page.getByTestId('boss-Stormterror');
	await expect(boss).toBeVisible();
	await boss.getByRole('checkbox', { name: 'Done this week' }).check();
	await expect(boss).toHaveClass(/done/);
	await page.reload();
	await expect(page.getByTestId('boss-Stormterror')).toHaveClass(/done/);
});

test('inventory To farm filter shows only short tiles', async ({ page }) => {
	await page.goto('/inventory');
	await expect(page.getByTestId('tile-104003')).toBeVisible(); // Hero's Wit, met
	await page.getByRole('button', { name: 'To farm' }).click();
	await expect(page.getByTestId('tile-104302')).toBeVisible(); // Guide to Freedom, short
	await expect(page.getByTestId('tile-104003')).toHaveCount(0);
	await expect(page.getByTestId('tile-100055')).toHaveCount(0); // unneeded
});
