import { expect, test } from '@playwright/test';

test('dashboard shows active domains and a weekly boss that can be ticked', async ({ page }) => {
	await page.goto('/');
	const today = page.getByTestId('domains');
	await expect(today.getByText('Domain of Mastery: Forsaken Rift', { exact: true })).toBeVisible();
	const boss = page.getByTestId('boss-Stormterror');
	await expect(boss).toBeVisible();
	await boss.getByRole('checkbox', { name: 'Done this week' }).check();
	await expect(boss).toHaveClass(/done/);
	await page.reload();
	await expect(page.getByTestId('boss-Stormterror')).toHaveClass(/done/);
});

test('inventory To farm strip lists short materials; backpack shows plain counts', async ({ page }) => {
	await page.goto('/inventory');
	const strip = page.getByTestId('to-farm');
	await expect(strip.getByTestId('farm-104302')).toBeVisible();          // Guide to Freedom, short
	await expect(strip.getByTestId('farm-104302')).toContainText('−');
	await expect(strip.getByTestId('farm-104003')).toHaveCount(0);         // Hero's Wit, met
	await expect(page.getByTestId('tile-104302')).toContainText('8');
	await expect(page.getByTestId('tile-104302').locator('.count')).not.toContainText('/');
	await expect(page.getByTestId('tile-104003')).toContainText('—');      // met, no scan: unknown
	await expect(page.getByTestId('tile-104003')).toHaveClass(/dim/);
	await expect(page.getByTestId('scan-hint')).toBeVisible();
	await expect(page.getByRole('button', { name: 'To farm' })).toHaveCount(0);
	await page.getByLabel('Search materials').fill('Freedom');
	await expect(strip).toHaveCount(0);
	await expect(page.getByTestId('tile-104302')).toBeVisible();
	await page.getByLabel('Search materials').fill('');
});

test('a stored Needed filter opens on All', async ({ page }) => {
	await page.goto('/inventory');
	await page.evaluate(() => localStorage.setItem('gt.inventory.filter', 'needed'));
	await page.reload();
	await expect(page.getByRole('button', { name: 'All', exact: true })).toHaveClass(/on/);
	await expect(page.getByTestId('tile-100055')).toBeVisible();           // unneeded tile still listed
	await page.evaluate(() => localStorage.removeItem('gt.inventory.filter'));
});
