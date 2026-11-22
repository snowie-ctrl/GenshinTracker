import { expect, test } from '@playwright/test';

test('profile shows stats, current Abyss and past runs', async ({ page }) => {
	await page.goto('/profile');
	await expect(page.getByText('AR 58')).toBeVisible();
	await expect(page.getByTestId('abyss-current')).toContainText('36');
	await expect(page.getByTestId('abyss-past').locator('tbody tr')).toHaveCount(2);
	await page.goto('/');
	await expect(page.getByTestId('dash-profile')).toContainText('AR 58');
});
