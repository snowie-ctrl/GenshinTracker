import { expect, test } from '@playwright/test';

test('wishes page shows pity tiles and tracks a weapon chart', async ({ page }) => {
	await page.goto('/wishes');
	const character = page.getByTestId('pity-character');
	await expect(character).toContainText('2 / 90');
	await expect(character.getByTestId('guaranteed')).toHaveCount(0);            // next 5★ is a 50/50
	await expect(character.getByTestId('avg-mark')).toHaveAttribute('title', 'Your average 5★ pity: 14');
	await expect(page.getByTestId('pity-weapon').getByTestId('avg-mark')).toHaveCount(0);   // no 5★ there
	const weapon = page.getByTestId('pity-weapon');
	await weapon.getByLabel('Charted weapon').selectOption({ label: 'Mistsplitter Reforged' });
	await expect(weapon.getByTestId('fate')).toContainText('Fate point 0/1');
	await page.reload();
	await expect(page.getByTestId('pity-weapon').getByTestId('fate')).toContainText('charted Mistsplitter Reforged');
});

test('banner filter drives the charts and the 5★ list', async ({ page }) => {
	await page.goto('/wishes');
	const filters = page.getByTestId('filters');
	await expect(filters.getByRole('button', { name: 'Character Event', pressed: true })).toBeVisible();
	await expect(page.getByTestId('five-list')).toContainText('Furina');
	await expect(page.getByTestId('luck')).toContainText('14');
	await expect(page.getByTestId('elements-radar')).toBeVisible();
	await expect(page.getByTestId('pity-hist')).toBeVisible();
	await expect(page.getByTestId('primogems')).toContainText('4,800');            // 30 character pulls × 160
	await page.getByTestId('pulls-chart').getByRole('button', { name: 'Rotation' }).click();
	await expect(page.getByTestId('pulls-chart')).toContainText('9.9 ph1');
	await filters.getByRole('button', { name: 'Standard' }).click();
	await expect(page.getByTestId('five-list')).toContainText('Kaedehara Kazuha');
	await expect(page.getByTestId('five-list')).not.toContainText('Furina');
	await page.reload();
	await expect(filters.getByRole('button', { name: 'Standard', pressed: true })).toBeVisible();  // remembered
	await page.getByTestId('pity-character').getByRole('button', { name: 'Character Event' }).click();
	await expect(filters.getByRole('button', { name: 'Character Event', pressed: true })).toBeVisible();
});

test('history rarity filter shows only 5★ rows', async ({ page }) => {
	await page.goto('/wishes');
	await expect(page.getByTestId('history-row').first()).toBeVisible();
	await page.getByLabel('Rarity').selectOption('5');
	await expect(page.getByTestId('history-row')).toHaveCount(3);
	for (const row of await page.getByTestId('history-row').all()) await expect(row).toContainText('5★');
});

test('dashboard shows pity on the live character banner', async ({ page }) => {
	await page.goto('/');
	await expect(page.getByTestId('dash-banners')).toContainText('Pity 2/90 · 50/50');
});
