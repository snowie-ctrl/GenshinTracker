import { expect, test } from '@playwright/test';

test('timeline bars open a popup that ticks Done, shown on the Dashboard', async ({ page }) => {
	await page.goto('/events');
	await expect(page.getByTestId('today-line')).toBeVisible();
	await expect(page.getByTestId('bar-ann:9001')).not.toHaveClass(/noart/);
	await expect(page.getByTestId('bar-cal:9003')).toHaveClass(/noart/);
	await expect(page.getByTestId('bar-ann:9100')).toHaveClass(/wish/);
	await expect(page.getByTestId('bar-ann:9102')).toHaveClass(/done|ended/);

	await page.getByTestId('bar-ann:9002').click();
	const modal = page.getByTestId('event-modal');
	await expect(modal).toBeVisible();
	await expect(modal).toContainText('Quick Trial');
	await expect(modal).toContainText('60 primos');
	await modal.getByRole('button', { name: 'Mark done' }).click();
	await expect(page.getByTestId('event-9002')).toHaveClass(/done/);
	await expect(page.getByTestId('timers')).not.toContainText('Quick Trial');
	await expect(page.getByTestId('events-left')).toContainText('2 events left · 420 primos unclaimed');
	await page.keyboard.press('Escape');
	await expect(modal).toBeHidden();
	await expect(page.getByTestId('bar-ann:9002')).toBeFocused();

	await page.goto('/');
	await expect(page.getByTestId('dash-event-9002')).toHaveClass(/done/);
	await expect(page.getByTestId('dash-banners')).toContainText('Tide of Furina');
	await page.goto('/events');
	await page.getByTestId('event-9002').getByRole('checkbox').uncheck();
	await expect(page.getByTestId('event-9002')).not.toHaveClass(/done/);
});

test('wish popup shows featured items; timers list resets and ending soon', async ({ page }) => {
	await page.goto('/events');
	const timers = page.getByTestId('timers');
	await expect(timers).toContainText('Spiral Abyss');
	await expect(timers.getByTestId('ending-soon')).toContainText('Quick Trial');
	await page.getByTestId('bar-ann:9100').click();
	const modal = page.getByTestId('event-modal');
	await expect(modal.getByRole('img', { name: 'Furina' })).toBeVisible();
	await expect(modal.getByRole('button', { name: 'Mark done' })).toHaveCount(0);
	await modal.getByRole('button', { name: 'Close' }).click();
	await expect(modal).toBeHidden();
});

test('banner history groups by version, pages on scroll and searches', async ({ page }) => {
	await page.goto('/events');
	const history = page.getByTestId('banner-history');
	const top = history.getByTestId('version-9.9');
	await expect(top).toContainText('Tide of Furina');
	await expect(top.getByTestId('phase').first()).toContainText('Phase 1');
	await expect(top.locator('.phase.upcoming')).toContainText('Next Phase Wish');
	await expect(history.getByTestId('version-1.0')).toHaveCount(0);
	await history.getByRole('button', { name: 'Load more' }).scrollIntoViewIfNeeded();
	await expect(history.getByTestId('version-1.0')).toBeVisible();
	await page.getByLabel('Search banners').fill('Epitome');
	await expect(history.getByTestId('version-9.9')).toContainText('Epitome Invocation');
	await expect(history.getByTestId('version-9.9')).not.toContainText('Tide of Furina');
	await expect(history.getByTestId('version-1.0')).toHaveCount(0);
	await page.getByLabel('Search banners').fill('');
});
