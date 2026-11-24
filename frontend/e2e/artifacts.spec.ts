import { expect, test } from '@playwright/test';

type Goal = { artifact_target: unknown; artifacts_done: boolean };

async function snapshot(page: import('@playwright/test').Page, slug: string): Promise<Goal & { id: number }> {
	const c = await (await page.request.get(`/api/characters/${slug}`)).json();
	return { id: c.id, artifact_target: c.artifact_target, artifacts_done: c.artifacts_done };
}

async function restore(page: import('@playwright/test').Page, g: Goal & { id: number }) {
	await page.request.put(`/api/characters/${g.id}/goal`,
		{ data: { artifact_target: g.artifact_target, artifacts_done: g.artifacts_done } });
}

test('Build tab sets a 4-piece target and main stats', async ({ page }) => {
	const original = await snapshot(page, 'furina');
	try {
		await page.goto('/characters/furina/build');
		const card = page.getByTestId('build-artifacts');
		await expect(card.getByTestId('artifact-set-0')).toHaveValue('15007');
		await expect(card.getByTestId('artifact-set-1')).toHaveValue('15001');
		await card.getByTestId('artifact-mode-4').click();
		await expect(card.getByTestId('artifact-set-1')).toHaveCount(0);
		await card.getByTestId('artifact-set-0').selectOption('15008');
		await card.getByTestId('stat-goblet-pyro').locator('button').click();      // no wait: builds on the draft
		await expect(card.getByTestId('artifact-source-0')).toHaveText('Clear Pool and Mountain Cavern');
		await expect(card.getByTestId('stat-goblet-pyro').locator('button')).toHaveAttribute('aria-pressed', 'true');
		await expect(card.getByTestId('stat-goblet-hydro').locator('button')).toHaveAttribute('aria-pressed', 'true');
		await expect(card.getByTestId('artifact-status')).toContainText('4pc Bloodstained Chivalry (0/4)');
		await card.getByTestId('sub-add').selectOption('em');
		await expect(card.getByTestId('sub-em')).toContainText('5');
		await card.getByTestId('sub-up-em').click();
		await expect(card.getByTestId('sub-em')).toContainText('4');
		await page.reload();
		await expect(page.getByTestId('artifact-set-0')).toHaveValue('15008');
	} finally {
		await restore(page, original);
	}
});

test('Dashboard lists the domain and Artifacts done removes the character', async ({ page }) => {
	const original = await snapshot(page, 'furina');
	try {
		await page.goto('/');
		const section = page.getByTestId('artifact-domains');
		await expect(section).toBeVisible();
		const card = section.getByTestId('artifact-domain-5101');
		await expect(card).toContainText('Clear Pool and Mountain Cavern');
		await expect(card.getByTestId('artifact-set-row-15007').getByRole('link')).toHaveAttribute('href', '/characters/furina/build');
		await expect(card.getByTestId('artifact-set-row-15008').getByRole('link')).toHaveAttribute('href', '/characters/neuvillette/build');
		await expect(section.getByTestId('artifact-other')).toContainText("Gladiator's Finale");
		await expect(section.locator('a[href="/characters/bennett/build"]')).toHaveCount(0);   // ticked done

		await page.goto('/characters/furina/build');
		await page.getByTestId('artifacts-done').check();
		await expect(page.getByTestId('artifacts-done')).toBeChecked();
		await page.goto('/');
		await expect(page.getByTestId('artifact-set-row-15007')).toHaveCount(0);
		await expect(page.getByTestId('artifact-other')).toHaveCount(0);
		await expect(page.getByTestId('artifact-set-row-15008')).toBeVisible();      // Neuvillette still needs it
	} finally {
		await restore(page, original);
	}
});
