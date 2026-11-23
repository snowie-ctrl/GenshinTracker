import { expect, test } from '@playwright/test';

test('create a Build team in the popup, then switch Build off from the row', async ({ page }) => {
	await page.goto('/teams');
	await page.getByTestId('new-team').click();
	await expect(page).toHaveURL(/\/teams\?edit=new$/);
	const dialog = page.getByRole('dialog');
	await dialog.getByLabel('Team name').fill('Dendro test');
	await dialog.getByTestId('pick-nahida').click();
	await expect(dialog.getByTestId('slot-0')).toContainText('Nahida');
	await dialog.getByRole('switch', { name: 'Build' }).click();
	await expect(dialog.getByText('Saving raises Nahida to Build')).toBeVisible();
	await dialog.getByLabel('Add tag').fill('dendro');
	await dialog.getByLabel('Add tag').press('Enter');
	await dialog.getByRole('button', { name: 'Save' }).click();

	await expect(page).toHaveURL(/\/teams$/);
	await expect(page.getByText('Raised 1 character to Build')).toBeVisible();
	const row = page.locator('article', { hasText: 'Dendro test' });
	await expect(row).toBeVisible();
	await page.getByTestId('tag-filter').getByRole('button', { name: 'dendro' }).click();
	await expect(page.locator('article')).toHaveCount(1);
	await page.getByTestId('tag-filter').getByRole('button', { name: 'All' }).click();

	await page.goto('/characters');
	await expect(page.getByTestId('section-building').getByTestId('card-nahida')).toBeVisible();

	await page.goto('/teams');
	page.once('dialog', (d) => d.accept());               // "Turn off Build? This moves Nahida off Build."
	await row.getByRole('switch', { name: 'Build' }).click();
	await expect(page.getByText('Moved 1 character off Build')).toBeVisible();
	await page.goto('/characters');
	await expect(page.getByTestId('section-obtained').getByTestId('card-nahida')).toBeVisible();

	// restore: delete the team and its tag
	await page.goto('/teams');
	await row.getByRole('button', { name: 'Edit Dendro test' }).click();
	page.once('dialog', (d) => d.accept());
	await page.getByRole('dialog').getByRole('button', { name: 'Delete team' }).click();
	await expect(page.locator('article', { hasText: 'Dendro test' })).toHaveCount(0);
	const tags = await (await page.request.get('/api/tags')).json();
	const dendro = tags.find((t: { name: string }) => t.name === 'dendro');
	if (dendro) await page.request.delete(`/api/tags/${dendro.id}`);
});

test('ribbons grey out unowned members; the shortfall drawer opens', async ({ page }) => {
	await page.goto('/teams');
	const team = page.getByTestId('team-1');
	await expect(team.getByTestId('ribbon-xingqiu')).toHaveClass(/unowned/);
	await expect(team.getByTestId('ribbon-xingqiu')).toContainText('Not owned');
	await expect(page.getByTestId('team-shortfall-1')).toHaveCount(0);
	await page.getByTestId('shortfall-toggle-1').click();
	await expect(page.getByTestId('team-shortfall-1')).toBeVisible();
});

test('hover arrows reorder; reordering is off while a tag filter is on', async ({ page }) => {
	await page.goto('/teams');
	const rows = page.locator('article[data-testid^="team-"]');
	await page.getByTestId('team-2').hover();
	await page.getByRole('button', { name: 'Move Archons only up' }).click();
	await expect(rows.first()).toHaveAttribute('data-testid', 'team-2');
	await page.getByTestId('team-2').hover();
	await page.getByRole('button', { name: 'Move Archons only down' }).click();   // restore
	await expect(rows.first()).toHaveAttribute('data-testid', 'team-1');

	await page.getByTestId('tag-filter').getByRole('button', { name: 'Abyss' }).click();
	await expect(page.getByTestId('reorder-hint')).toBeVisible();
	await expect(page.getByRole('button', { name: 'Move Abyss Furina down' })).toBeDisabled();
	await page.getByTestId('tag-filter').getByRole('button', { name: 'All' }).click();
});

test('old editor URLs open the popup; errors sit by their field; Delete names the saved team', async ({ page }) => {
	await page.goto('/teams/new');
	await expect(page).toHaveURL(/\/teams\?edit=new$/);
	await page.getByRole('dialog').getByRole('button', { name: 'Close' }).click();

	await page.goto('/teams/2');
	await expect(page).toHaveURL(/\/teams\?edit=2$/);
	const dialog = page.getByRole('dialog');
	await expect(dialog.getByLabel('Team name')).toHaveValue('Archons only');
	await dialog.getByLabel('Team name').fill('');
	await dialog.getByRole('button', { name: 'Save' }).click();
	await expect(dialog.getByTestId('error-name')).toHaveText('Team name is required');
	await dialog.getByLabel('Team name').fill('Renamed but unsaved');
	let message = '';
	page.once('dialog', (d) => { message = d.message(); void d.dismiss(); });
	await dialog.getByRole('button', { name: 'Delete team' }).click();
	await expect.poll(() => message).toContain('"Archons only"');
});

test('popup asks before discarding unsaved changes', async ({ page }) => {
	await page.goto('/teams');
	await page.getByRole('button', { name: 'Edit Archons only' }).click();   // so /teams sits behind ?edit=2 in history
	await expect(page).toHaveURL(/\/teams\?edit=2$/);
	const dialog = page.getByRole('dialog');
	await dialog.getByLabel('Team name').fill('Changed');
	let asked = '';
	page.once('dialog', (d) => { asked = d.message(); void d.dismiss(); });
	await page.keyboard.press('Escape');
	await expect.poll(() => asked).toContain('Discard changes?');
	await expect(dialog).toBeVisible();
	page.once('dialog', (d) => d.accept());
	await page.goBack();
	await expect(page.getByRole('dialog')).toHaveCount(0);
	await expect(page.getByTestId('team-2')).toContainText('Archons only');
});

test('closing returns focus to the row; a repeated Escape still asks and never strands the popup', async ({ page }) => {
	await page.goto('/teams');
	const edit = page.getByRole('button', { name: 'Edit Archons only' });
	await edit.click();
	const dialog = page.getByRole('dialog');
	await expect(dialog.getByLabel('Team name')).toHaveValue('Archons only');
	await dialog.getByRole('button', { name: 'Cancel' }).click();
	await expect(page).toHaveURL(/\/teams$/);
	await expect(page.getByRole('dialog')).toHaveCount(0);
	await expect(edit).toBeFocused();

	await edit.click();
	await dialog.getByLabel('Team name').fill('Changed');
	const asked: string[] = [];
	page.on('dialog', (d) => { asked.push(d.message()); void (asked.length < 3 ? d.dismiss() : d.accept()); });
	// Only node-side polls between these two presses: locator assertions run page scripts with a user
	// gesture, which would make the second Escape cancelable again and hide the native-close path.
	await page.keyboard.press('Escape');                 // cancelable: the cancel handler asks
	await expect.poll(() => asked.length).toBe(1);
	await page.keyboard.press('Escape');                 // no user activation since: Chromium closes natively, the close handler asks
	await expect.poll(() => asked.length).toBe(2);
	await expect(dialog).toBeVisible();
	await expect(page).toHaveURL(/\/teams\?edit=2$/);
	await page.keyboard.press('Escape');                 // accepted this time
	await expect.poll(() => asked.length).toBe(3);
	expect(asked.every((m) => m.includes('Discard changes?'))).toBe(true);
	await expect(page).toHaveURL(/\/teams$/);
	await expect(page.getByRole('dialog')).toHaveCount(0);
	await expect(page.getByTestId('team-2')).toContainText('Archons only');
	await expect(edit).toBeFocused();
});

test('a rejected tag rename restores the old name; a deleted tag leaves the filter', async ({ page }) => {
	await page.goto('/teams');
	await page.getByRole('button', { name: 'Manage tags' }).click();
	const manager = page.getByTestId('tag-manager');
	const rename = manager.getByLabel('Rename Abyss');
	await rename.fill('Build');
	await rename.press('Tab');
	await expect(manager.locator('.error')).toBeVisible();
	await expect(rename).toHaveValue('Abyss');

	await manager.getByLabel('New tag name').fill('scratch');
	await manager.getByRole('button', { name: 'Add tag' }).click();
	const filter = page.getByTestId('tag-filter');
	await filter.getByRole('button', { name: 'scratch' }).click();
	await expect(page.getByText('No team has these tags.')).toBeVisible();
	page.once('dialog', (d) => d.accept());
	await manager.locator('li', { hasText: 'scratch' }).getByRole('button', { name: 'Delete' }).click();
	await expect(filter.getByRole('button', { name: 'scratch' })).toHaveCount(0);
	await expect(filter.getByRole('button', { name: 'All' })).toHaveClass(/on/);
});
