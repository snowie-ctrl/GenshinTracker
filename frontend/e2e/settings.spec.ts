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

test('settings are grouped with an index that jumps to each section', async ({ page }) => {
	await page.goto('/settings');
	const index = page.getByRole('navigation', { name: 'Settings sections' });
	for (const label of ['Account', 'Sync & data', 'Appearance', 'Planner', 'Wishes', 'Map']) {
		await expect(index.getByRole('link', { name: label })).toBeVisible();
		await expect(page.getByRole('heading', { level: 2, name: label })).toBeVisible();
	}
	await index.getByRole('link', { name: 'Map' }).click();
	await expect(page).toHaveURL(/#map$/);
	await expect(page.getByLabel('Default map')).toBeInViewport();
});

test('turning the animated background off is remembered across reloads', async ({ page }) => {
	await page.goto('/settings');
	const toggle = page.getByLabel('Animated background');
	await expect(toggle).toBeChecked();
	await expect(page.getByTestId('starfield')).toHaveAttribute('data-animated', 'true');
	await toggle.uncheck();
	await expect(page.getByTestId('starfield')).toHaveAttribute('data-animated', 'false');
	await page.reload();
	await expect(page.getByLabel('Animated background')).not.toBeChecked();
	await expect(page.getByTestId('starfield')).toHaveAttribute('data-animated', 'false');
	await page.getByLabel('Animated background').check(); // leave the seed as we found it
	await expect(page.getByTestId('starfield')).toHaveAttribute('data-animated', 'true');
});

test('reduced motion keeps the background still even with the setting on', async ({ page }) => {
	await page.emulateMedia({ reducedMotion: 'reduce' });
	await page.goto('/settings');
	await expect(page.getByLabel('Animated background')).toBeChecked();
	await expect(page.getByTestId('starfield')).toHaveAttribute('data-animated', 'false');
});

test('a failed background save snaps the toggle back and shows the error', async ({ page }) => {
	await page.goto('/settings');
	await page.route('**/api/settings', (route) =>
		route.request().method() === 'GET'
			? route.continue()
			: route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'Save failed' }) })
	);
	const toggle = page.getByLabel('Animated background');
	await toggle.uncheck();
	await expect(page.getByTestId('appearance-note')).toHaveText('Save failed');
	await expect(toggle).toBeChecked();
	await expect(page.getByTestId('starfield')).toHaveAttribute('data-animated', 'true');
});

test('display name saves and trims', async ({ page }) => {
	await page.goto('/settings');
	const input = page.getByTestId('display-name');
	await input.fill('  Lumine  ');
	await input.blur();
	await expect(page.getByTestId('display-name-note')).toHaveText('Saved');
	await expect(input).toHaveValue('Lumine');
	await input.fill('');
	await input.blur();
	await expect(input).toHaveValue('');
});
