import { expect, test } from '@playwright/test';

test('ticking an event Done dims it and lowers the Dashboard count', async ({ page }) => {
	await page.goto('/');
	await expect(page.getByTestId('dash-events')).toContainText('3 events left · 480 primos');
	await page.goto('/events');
	const row = page.getByTestId('event-9002');
	await row.getByRole('checkbox').check();
	await expect(row).toHaveClass(/done/);
	await expect(page.getByTestId('events-left')).toContainText('2 left · 420 primos unclaimed');
	await page.goto('/');
	await expect(page.getByTestId('dash-events')).toContainText('2 events left · 420 primos');
	await expect(page.getByTestId('dash-banners')).toContainText('Tide of Furina');
	await expect(page.getByTestId('dash-resets')).toContainText('Spiral Abyss');
});

test('banner history search narrows the list', async ({ page }) => {
	await page.goto('/events');
	await page.getByLabel('Search banners').fill('Furina');
	await expect(page.getByTestId('banner-history').locator('tbody tr').first()).toContainText('Tide of Furina');
});
