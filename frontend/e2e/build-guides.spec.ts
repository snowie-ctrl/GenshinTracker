import { expect, test } from '@playwright/test';

type Snap = { id: number; goal: string; artifact_target: unknown; artifacts_done: boolean };

async function snapshot(page: import('@playwright/test').Page, slug: string): Promise<Snap> {
	const c = await (await page.request.get(`/api/characters/${slug}`)).json();
	return { id: c.id, goal: c.goal, artifact_target: c.artifact_target, artifacts_done: c.artifacts_done };
}

async function restore(page: import('@playwright/test').Page, s: Snap) {
	await page.request.put(`/api/characters/${s.id}/goal`, { data: { goal: s.goal } });
	await page.request.put(`/api/characters/${s.id}/goal`,
		{ data: { artifact_target: s.artifact_target, artifacts_done: s.artifacts_done } });
}

test('Build suggestions show HoYoLAB stats and Apply updates the target', async ({ page }) => {
	const original = await snapshot(page, 'bennett');
	try {
		await page.goto('/characters/bennett/build');
		const card = page.getByTestId('build-suggestions');
		await expect(card).toContainText('HoYoLAB recommends');
		await expect(card.getByTestId('suggestion-sands-er')).toBeVisible();
		await expect(card.getByTestId('suggestion-sub-hp')).toBeVisible();
		await card.getByTestId('suggestions-apply').click();
		await expect(card.getByTestId('suggestions-match')).toBeVisible();
		const arts = page.getByTestId('build-artifacts');
		await expect(arts.getByTestId('stat-goblet-pyro').locator('button')).toHaveAttribute('aria-pressed', 'true');
		await expect(arts.getByTestId('artifact-set-0')).toHaveValue('15007');           // sets kept
	} finally {
		await restore(page, original);
	}
});

test('Build suggestions say when the target already matches', async ({ page }) => {
	await page.goto('/characters/furina/build');
	await expect(page.getByTestId('suggestions-match')).toBeVisible();
	await expect(page.getByTestId('suggestions-apply')).toHaveCount(0);
});

test('Build suggestions empty state', async ({ page }) => {
	await page.goto('/characters/neuvillette/build');
	await expect(page.getByTestId('suggestions-empty')).toContainText('No HoYoLAB recommendation yet');
});

test('Setting Build prefills the artifact target from the recommendation', async ({ page }) => {
	const original = await snapshot(page, 'xiangling');
	try {
		await page.goto('/characters/xiangling/build');
		await expect(page.getByTestId('suggestions-apply')).toHaveCount(0);              // not Build: read-only
		await page.getByTestId('set-build').click();
		const arts = page.getByTestId('build-artifacts');
		await expect(arts.getByTestId('stat-sands-em').locator('button')).toHaveAttribute('aria-pressed', 'true');
		await expect(page.getByTestId('suggestions-match')).toBeVisible();
	} finally {
		await restore(page, { ...original, artifact_target: null });
	}
});

test('Guide links to the community build guide', async ({ page }) => {
	await page.goto('/characters/bennett/guide');
	const link = page.getByTestId('community-guide-link');
	await expect(link).toHaveAttribute('href', 'https://genshin-impact-helper-team.github.io/genshin-builds/en/bennett');
	await expect(link).toHaveAttribute('target', '_blank');
	await expect(link).toHaveAttribute('rel', 'noopener noreferrer');
	await expect(page.getByTestId('guide-howto')).toContainText('not affiliated with Ad Astra');
});
