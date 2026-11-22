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

test('reordering is off while a tag filter is on', async ({ page }) => {
	await page.goto('/teams');
	await expect(page.getByRole('button', { name: 'Move Archons only up' })).toBeEnabled();
	await page.getByTestId('tag-filter').getByRole('button', { name: 'abyss' }).click();
	await expect(page.getByTestId('reorder-hint')).toBeVisible();
	await expect(page.getByRole('button', { name: 'Move Abyss Furina down' })).toBeDisabled();
	await page.getByTestId('tag-filter').getByRole('button', { name: 'All' }).click();
	await expect(page.getByTestId('reorder-hint')).toHaveCount(0);
});

test('a rejected tag rename restores the old name; a deleted tag leaves the filter', async ({ page }) => {
	await page.goto('/teams');
	await page.getByRole('button', { name: 'Manage tags' }).click();
	const manager = page.getByTestId('tag-manager');
	const rename = manager.getByLabel('Rename abyss');
	await rename.fill('Build');
	await rename.press('Tab');
	await expect(manager.locator('.error')).toBeVisible();
	await expect(rename).toHaveValue('abyss');

	await manager.getByLabel('New tag name').fill('scratch');
	await manager.getByRole('button', { name: 'Add tag' }).click();
	const filter = page.getByTestId('tag-filter');
	await filter.getByRole('button', { name: 'scratch' }).click();
	await expect(page.getByText('No team has these tags.')).toBeVisible();
	page.once('dialog', (d) => d.accept());
	await manager.locator('li', { hasText: 'scratch' }).getByRole('button', { name: 'Delete' }).click();
	await expect(filter.getByRole('button', { name: 'scratch' })).toHaveCount(0);
	await expect(filter.getByRole('button', { name: 'All' })).toHaveClass(/on/);
	await expect(page.getByText('No team has these tags.')).toHaveCount(0);
});

test('team editor errors sit by their field; Delete names the saved team', async ({ page }) => {
	await page.goto('/teams/2');
	await page.getByLabel('Team name').fill('');
	await page.getByRole('button', { name: 'Save' }).click();
	await expect(page.getByTestId('error-name')).toHaveText('Team name is required');
	await page.getByLabel('Team name').fill('Renamed but unsaved');
	let message = '';
	page.once('dialog', (d) => {
		message = d.message();
		void d.dismiss();
	});
	await page.getByRole('button', { name: 'Delete team' }).click();
	await expect.poll(() => message).toContain('"Archons only"');
});
