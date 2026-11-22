import { expect, test } from '@playwright/test';

test('a failed Default map save snaps the select back to the saved value', async ({ page }) => {
	await page.goto('/settings');
	const select = page.getByLabel('Default map');
	const saved = await select.inputValue();
	const other = saved === 'hoyolab' ? 'appsample' : 'hoyolab';
	await page.route('**/api/settings', (route) =>
		route.request().method() === 'GET'
			? route.continue()
			: route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'Save failed' }) })
	);
	await select.selectOption(other);
	await expect(page.getByText('Save failed')).toBeVisible();
	await expect(select).toHaveValue(saved);
});
