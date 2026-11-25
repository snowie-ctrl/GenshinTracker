import { expect, test } from '@playwright/test';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const fixture = resolve(dirname(fileURLToPath(import.meta.url)), 'fixtures', 'good-sample.json');

test('GOOD import: opt in, import, exact counts, weapons, artifacts, opt out', async ({ page }) => {
	await page.goto('/inventory');
	await expect(page.getByTestId('gap-status')).toBeVisible();                            // page loaded
	await expect(page.getByRole('button', { name: 'Import GOOD file' })).toHaveCount(0);   // off by default

	await page.goto('/settings');
	await Promise.all([
		page.waitForResponse((r) => r.url().includes('/api/settings') && r.request().method() === 'PUT' && r.ok()),
		page.getByTestId('good-settings').getByRole('checkbox', { name: 'Use GOOD inventory import' }).check(),
	]);
	await expect(page.getByTestId('good-settings').getByRole('button', { name: 'Import GOOD file' })).toBeVisible();

	await page.goto('/inventory');
	await page.getByTestId('good-file-input').setInputFiles(fixture);
	await expect(page.getByTestId('good-toast')).toContainText('Imported 5 materials, 2 weapons, 3 artifacts.');
	await expect(page.getByTestId('scan-status')).toContainText('E2E_Scanner');

	const lamp = page.getByTestId('tile-100055');           // unneeded, now owned
	await expect(lamp).toContainText('37');
	await expect(lamp).not.toHaveClass(/dim/);
	await expect(page.getByTestId('tile-104003')).toContainText('120');      // met: scan count
	await expect(page.getByTestId('tile-104003').locator('.count')).not.toContainText('✓');
	await expect(page.getByTestId('tile-104302')).toContainText('8');        // short: live wins over scan 2
	await expect(page.getByTestId('tile-104302').locator('.count')).not.toContainText('/');
	await expect(page.getByTestId('tile-101301')).toContainText('250');      // Birch Wood from the scan
	await expect(page.getByTestId('tile-101301')).not.toHaveClass(/dim/);
	await expect(page.getByTestId('tile-101401')).toContainText('40');       // Fabric

	await page.getByRole('button', { name: 'Owned', exact: true }).click();
	await expect(page.getByTestId('tile-100055')).toBeVisible();
	await expect(page.getByTestId('tile-101301')).toBeVisible();            // scanned teapot tile kept
	await expect(page.getByTestId('tile-101302')).toHaveCount(0);           // Cuihua Wood: not in the scan
	await expect(page.getByTestId('tile-104319')).toHaveCount(0);           // Crown: not in the scan
	await page.getByRole('button', { name: 'All', exact: true }).click();

	await page.getByRole('tab', { name: 'Weapons', exact: true }).click();
	const mist = page.getByTestId('weapon-card').filter({ hasText: 'Mistsplitter Reforged' });
	await expect(mist).toContainText('Unequipped');
	await expect(page.getByTestId('weapon-card').filter({ hasText: 'Favonius Sword' })).toContainText('Bennett');
	await page.getByRole('checkbox', { name: 'Unequipped only' }).check();
	await expect(page.getByTestId('weapon-card')).toHaveCount(1);

	await page.getByRole('tab', { name: 'Artifacts', exact: true }).click();
	await expect(page.getByTestId('artifact-count')).toHaveText('3 artifacts · 2 unequipped');
	await expect(page.getByTestId('artifact-card')).toHaveCount(3);
	await page.getByRole('combobox', { name: 'Slot', exact: true }).selectOption('goblet');
	await expect(page.getByTestId('artifact-card')).toHaveCount(1);
	await expect(page.getByTestId('artifact-card')).toContainText('Pyro DMG Bonus');

	await page.goto('/settings');
	await Promise.all([
		page.waitForResponse((r) => r.url().includes('/api/settings') && r.request().method() === 'PUT' && r.ok()),
		page.getByTestId('good-settings').getByRole('checkbox', { name: 'Use GOOD inventory import' }).uncheck(),
	]);
	await page.goto('/inventory');
	await expect(page.getByTestId('tile-100055')).toHaveClass(/dim/);      // data loaded
	await expect(page.getByTestId('tile-100055')).not.toContainText('37');
	await expect(page.getByTestId('tile-101301')).toContainText('—');
	await expect(page.getByRole('tab', { name: 'Weapons', exact: true })).toHaveCount(0);
	await expect(page.getByRole('tab', { name: 'Artifacts', exact: true })).toHaveCount(0);
	await expect(page.getByRole('button', { name: 'Import GOOD file' })).toHaveCount(0);
});
