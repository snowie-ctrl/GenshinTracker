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

test('map tabs are a proper tablist controlling one tabpanel', async ({ page }) => {
	await page.goto('/map');
	const tab = page.getByRole('tab', { name: 'AppSample' });
	await tab.click();
	await expect(tab).toHaveAttribute('aria-selected', 'true');
	await expect(page.getByRole('tab', { name: 'HoYoLAB Interactive Map' })).toHaveAttribute('aria-selected', 'false');
	await expect(tab).toHaveAttribute('aria-controls', 'map-panel');
	await expect(page.getByRole('tabpanel', { name: 'AppSample' })).toBeVisible();
});

test('map tabs use a roving tabindex and arrow keys', async ({ page }) => {
	await page.goto('/map');
	const hoyolab = page.getByRole('tab', { name: 'HoYoLAB Interactive Map' });
	const appsample = page.getByRole('tab', { name: 'AppSample' });
	await hoyolab.click();
	await expect(hoyolab).toHaveAttribute('tabindex', '0');
	await expect(appsample).toHaveAttribute('tabindex', '-1');
	await page.keyboard.press('ArrowRight');
	await expect(appsample).toBeFocused();
	await expect(appsample).toHaveAttribute('aria-selected', 'true');
	await expect(appsample).toHaveAttribute('tabindex', '0');
	await expect(page.getByTestId('map-frame')).toHaveAttribute('src', /appsample/);
	await page.keyboard.press('ArrowLeft');
	await expect(hoyolab).toBeFocused();
	await expect(hoyolab).toHaveAttribute('aria-selected', 'true');
});

test('the embedded map fills most of the window', async ({ page }) => {
	await page.setViewportSize({ width: 1400, height: 900 });
	await page.goto('/map');
	await page.getByTestId('map-tab-appsample').click();
	const box = await page.getByTestId('map-frame').boundingBox();
	expect(box).not.toBeNull();
	expect(box!.height).toBeGreaterThan(900 * 0.8);
	expect(box!.width).toBeGreaterThan((1400 - 76) * 0.9);
});
