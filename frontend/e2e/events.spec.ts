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
	const history = page.getByTestId('banner-history');
	// control: the seeded weapon banner is listed in the weapon pool before searching
	await history.getByRole('button', { name: 'weapon' }).click();
	await expect(history.locator('tbody')).toContainText('Epitome Invocation');
	await history.getByRole('button', { name: 'character' }).click();
	await page.getByLabel('Search banners').fill('Furina');
	await expect(history.locator('tbody tr').first()).toContainText('Tide of Furina');
	await expect(history.locator('tbody tr')).toHaveCount(1);
	await expect(history.locator('tbody')).not.toContainText('Epitome Invocation');
	// searching Furina in the weapon pool finds nothing: the weapon banner does not match
	await history.getByRole('button', { name: 'weapon' }).click();
	await expect(history.locator('tbody')).toContainText('No banners match.');
	await expect(history.locator('tbody')).not.toContainText('Epitome Invocation');
});
