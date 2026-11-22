import { expect, test } from '@playwright/test';

const PAGES = [
	['Dashboard', '/'], ['Characters', '/characters'], ['Teams', '/teams'], ['Inventory', '/inventory'],
	['Map', '/map'], ['Events', '/events'], ['Wishes', '/wishes'], ['Profile', '/profile'], ['Settings', '/settings']
] as const;

test('the sidebar reaches every page and marks only the current one', async ({ page }) => {
	await page.goto('/');
	const nav = page.getByRole('navigation', { name: 'Main' });
	await expect(nav.getByRole('img', { name: 'Ad Astra' })).toBeVisible();
	for (const [label, path] of PAGES) {
		await nav.getByRole('link', { name: label, exact: true }).click();
		await expect(page).toHaveURL(new RegExp(`${path === '/' ? '/$' : path + '$'}`));
		await expect(nav.locator('[aria-current="page"]')).toHaveCount(1);
		await expect(nav.getByRole('link', { name: label, exact: true })).toHaveAttribute('aria-current', 'page');
	}
});

test('a nested character page keeps Characters active', async ({ page }) => {
	await page.goto('/characters/xiangling');
	const nav = page.getByRole('navigation', { name: 'Main' });
	await expect(nav.getByRole('link', { name: 'Characters', exact: true })).toHaveAttribute('aria-current', 'page');
	await expect(nav.getByRole('link', { name: 'Dashboard', exact: true })).not.toHaveAttribute('aria-current', 'page');
});

test('the sync item opens details with a Sync now button', async ({ page }) => {
	await page.goto('/');
	await page.getByTestId('sync-label').click();
	await expect(page.getByTestId('sync-popover')).toBeVisible();
	await expect(page.getByTestId('sync-popover').getByRole('button', { name: 'Sync now' })).toBeVisible();
	await page.getByTestId('sync-label').click();
	await expect(page.getByTestId('sync-popover')).toHaveCount(0);
});
