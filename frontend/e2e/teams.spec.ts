import { expect, test } from '@playwright/test';

test('a new Build team raises its member and appears with a shortfall panel', async ({ page }) => {
	await page.goto('/teams');
	await expect(page.getByTestId('team-1')).toBeVisible();
	await expect(page.getByTestId('team-shortfall-1')).toBeVisible();

	await page.getByTestId('new-team').click();
	await page.getByLabel('Team name').fill('Dendro test');
	await page.getByTestId('pick-nahida').click();
	await expect(page.getByTestId('slot-0')).toContainText('Nahida');
	await page.getByRole('button', { name: 'Build', exact: true }).click();
	await expect(page.getByText('Saving raises Nahida to Build')).toBeVisible();
	await page.getByLabel('Add tag').fill('dendro');
	await page.getByLabel('Add tag').press('Enter');
	await page.getByRole('button', { name: 'Save' }).click();

	await expect(page).toHaveURL(/\/teams/);
	await expect(page.getByText('Raised 1 character to Build')).toBeVisible();
	const card = page.locator('article', { hasText: 'Dendro test' });
	await expect(card).toBeVisible();
	await expect(card.locator('[data-testid^="team-shortfall-"]')).toBeVisible();

	await page.getByTestId('tag-filter').getByRole('button', { name: 'dendro' }).click();
	await expect(page.locator('article')).toHaveCount(1);
	await page.getByTestId('tag-filter').getByRole('button', { name: 'All' }).click();
	await expect(page.locator('article')).toHaveCount(3);

	await page.goto('/characters');
	await expect(page.getByTestId('section-building').getByTestId('card-nahida')).toBeVisible();
});
