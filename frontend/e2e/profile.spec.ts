import { expect, test } from '@playwright/test';

test('profile shows header, stats, exploration, roster, teapot, bosses and challenges', async ({ page }) => {
	await page.goto('/profile');
	await expect(page.getByText('AR 58')).toBeVisible();
	await expect(page.getByTestId('profile-header')).toContainText('Traveler');
	await expect(page.getByTestId('profile-header')).toContainText('900 days active');
	await expect(page.getByTestId('stat-tiles')).toContainText('Spiral Abyss');
	await expect(page.getByTestId('stat-tiles')).toContainText('12-3');
	await expect(page.getByTestId('region-card')).toHaveCount(3);
	await page.getByRole('button', { name: 'Show 2 areas' }).click();
	await expect(page.getByTestId('region-card').first()).toContainText('Galesong Hill');
	await expect(page.getByTestId('roster')).toContainText('5 characters');
	await expect(page.getByTestId('teapot')).toContainText('Lv 10');
	await expect(page.getByTestId('bosses').locator('li').first()).toContainText('Anemo Hypostasis');
	await expect(page.getByTestId('abyss-current')).toContainText('36');
	await expect(page.getByTestId('abyss-past').locator('tbody tr')).toHaveCount(2);
	await expect(page.getByTestId('abyss-past').getByRole('columnheader')).toHaveText(['Started', 'Result']);
});

test('showcase opens a detail panel and can be edited, then reset', async ({ page, request }) => {
	await page.goto('/profile');
	const cards = page.getByTestId('showcase-card');
	await expect(cards).toHaveCount(5);
	await expect(cards.first()).toContainText('Cryo Traveler');                 // automatic order
	await expect(page.getByTestId('showcase-panel')).toContainText('Favonius Sword');
	await cards.nth(1).click();
	await expect(page.getByTestId('showcase-panel')).toContainText('Furina');

	try {
		await page.getByRole('button', { name: 'Edit showcase' }).click();
		const editor = page.getByTestId('showcase-editor');
		await editor.getByRole('button', { name: 'Clear' }).click();
		await editor.getByRole('button', { name: 'Furina', exact: true }).click();
		await editor.getByRole('button', { name: 'Bennett', exact: true }).click();
		await editor.getByRole('button', { name: 'Move Bennett up' }).click();
		await editor.getByRole('button', { name: 'Save' }).click();
		await expect(cards).toHaveCount(2);
		await expect(cards.first()).toContainText('Bennett');
		await page.reload();
		await expect(page.getByTestId('showcase-card').first()).toContainText('Bennett');    // stored
		await page.getByRole('button', { name: 'Edit showcase' }).click();
		await page.getByTestId('showcase-editor').getByRole('button', { name: 'Reset to automatic' }).click();
		await expect(page.getByTestId('showcase-card')).toHaveCount(5);
	} finally {
		await request.put('/api/profile/showcase', { data: { ids: [] } });          // restore shared state
	}
});
