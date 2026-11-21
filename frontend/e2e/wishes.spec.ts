import { expect, test } from '@playwright/test';

test('wishes page shows pity and tracks a weapon chart', async ({ page }) => {
	await page.goto('/wishes');
	const character = page.getByTestId('pity-character');
	await expect(character).toContainText(/2\s*\/\s*90/);
	await expect(character).toContainText('Next 5★: 50/50');
	await page.getByRole('tab', { name: 'Weapon Event' }).click();
	await expect(page.getByTestId('tab-weapon')).toContainText('Pulls');
	const weapon = page.getByTestId('pity-weapon');
	await weapon.getByLabel('Charted weapon').selectOption({ label: 'Mistsplitter Reforged' });
	await expect(weapon.getByTestId('fate')).toContainText('Fate point 0/1');
	await page.reload();
	await expect(page.getByTestId('pity-weapon').getByTestId('fate')).toContainText('charted Mistsplitter Reforged');
});

test('history rarity filter shows only 5★ rows', async ({ page }) => {
	await page.goto('/wishes');
	await expect(page.getByTestId('history-row').first()).toBeVisible();
	await page.getByLabel('Rarity').selectOption('5');
	await expect(page.getByTestId('history-row')).toHaveCount(3);
	for (const row of await page.getByTestId('history-row').all()) await expect(row).toContainText('5★');
});

test('dashboard shows the pity card', async ({ page }) => {
	await page.goto('/');
	await expect(page.getByTestId('pity-card')).toContainText('Character 2/90 · 50/50');
});
