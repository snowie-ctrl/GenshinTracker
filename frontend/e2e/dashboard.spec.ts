import { expect, test } from '@playwright/test';

test('dashboard shows every section in order', async ({ page }) => {
	await page.goto('/');
	await expect(page.getByTestId('greeting')).toContainText(/Good (morning|afternoon|evening), /);
	for (const id of ['bubble-resin', 'bubble-commissions', 'bubble-realm', 'bubble-expeditions', 'ending-soon',
		'domains', 'weekly-bosses', 'builds', 'completed', 'timers', 'dash-banners', 'dash-events']) {
		await expect(page.getByTestId(id)).toBeVisible();
	}
	await expect(page.getByTestId('bubble-commissions')).toContainText('Bonus not claimed');
	await expect(page.getByTestId('bubble-expeditions')).toContainText('1/5 ready');
	await expect(page.getByTestId('completed')).toContainText('Neuvillette');
	await expect(page.getByTestId('timers')).toContainText('Parametric Transformer');
	await expect(page.getByTestId('timers')).toContainText('Ready');
	await expect(page.getByTestId('ending-soon')).toContainText('Photo Event');
	await expect(page.getByTestId('dash-event-9004').getByRole('checkbox')).toBeDisabled();   // finished in game
	await expect(page.getByTestId('dash-events')).toContainText('Stygian Onslaught');
});

test('day picker switches the viewed day and keeps today marked', async ({ page }) => {
	await page.goto('/');
	const domains = page.getByTestId('domains');
	const today = domains.locator('button.day.today');
	await expect(today).toHaveAttribute('aria-pressed', 'true');
	const todayId = await today.getAttribute('data-testid');
	const other = todayId === 'day-0' ? 'day-1' : 'day-0';
	await page.getByTestId(other).click();
	await expect(page.getByTestId(other)).toHaveAttribute('aria-pressed', 'true');
	await expect(page.getByTestId(todayId!)).toHaveAttribute('aria-pressed', 'false');
	await expect(page.getByTestId(todayId!)).toHaveClass(/today/);
	await expect(domains).toContainText('Domain of Mastery: Forsaken Rift');      // open every day in the seed
	await domains.getByRole('button', { name: 'Today' }).click();
	await expect(page.getByTestId(todayId!)).toHaveAttribute('aria-pressed', 'true');
});

test('moving a character up re-allocates counts, then moving back restores them', async ({ page }) => {
	await page.goto('/');
	const benGuide = page.getByTestId('build-bennett-104302');
	const furGuide = page.getByTestId('build-furina-104302');
	await expect(benGuide).toContainText('8/9');
	await expect(benGuide).toContainText('+1 craft');
	await expect(furGuide).toContainText('0/6');
	await expect(furGuide).toContainText('+2 craft');
	await page.getByRole('button', { name: 'Move Furina up' }).click();
	await expect(page.getByTestId('build-card-furina')).toContainText('P1');
	await expect(furGuide).toContainText('6/6');
	await expect(benGuide).toContainText('2/9');
	await expect(benGuide).toContainText('+3 craft');
	await page.reload();
	await expect(page.getByTestId('build-card-furina')).toContainText('P1');      // saved
	await page.getByRole('button', { name: 'Move Furina down' }).click();
	await expect(page.getByTestId('build-card-bennett')).toContainText('P1');
	await expect(benGuide).toContainText('8/9');
});

test('a failed reorder rolls back and shows an error', async ({ page }) => {
	await page.goto('/');
	await expect(page.getByTestId('build-card-bennett')).toContainText('P1');
	await page.route('**/api/priority', (r) =>
		r.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'boom' }) })
	);
	await page.getByRole('button', { name: 'Move Furina up' }).click();
	await expect(page.getByTestId('builds').getByRole('alert')).toBeVisible();
	await expect(page.getByTestId('build-card-bennett')).toContainText('P1');
	await expect(page.getByTestId('build-card-furina')).not.toContainText('P1');
});

test('ticking an event done drops it from ending soon, and unticking brings it back', async ({ page }) => {
	await page.goto('/');
	const box = page.getByTestId('dash-event-9003').getByRole('checkbox');
	await expect(page.getByTestId('ending-soon')).toContainText('Photo Event');
	try {
		await box.check();
		await expect(page.getByTestId('ending-soon')).not.toContainText('Photo Event');
	} finally {
		if (await box.isChecked()) await box.uncheck();
	}
	await expect(page.getByTestId('ending-soon')).toContainText('Photo Event');
});
