import { expect, test } from '@playwright/test';

test('a map that refuses embedding shows the fallback card; the other embeds', async ({ page }) => {
	await page.goto('/map');
	await page.getByTestId('map-tab-hoyolab').click();
	const fallback = page.getByTestId('map-fallback');
	await expect(fallback).toContainText("This map doesn't allow embedding");
	await expect(fallback.getByRole('link', { name: 'Open in new tab' })).toHaveAttribute('href', /act\.hoyolab\.com/);
	await page.getByTestId('map-tab-appsample').click();
	await expect(page.getByTestId('map-frame')).toHaveAttribute('src', /appsample/);
});
