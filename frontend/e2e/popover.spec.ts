import { expect, test } from '@playwright/test';

// Panels are backdrop-filtered (stacking contexts), so a tile's popover must lift its own panel
// above the following panels or it is painted underneath them.
for (const path of ['/', '/inventory']) {
	test(`material popovers paint above the following panels on ${path}`, async ({ page }) => {
		await page.goto(path);
		const tiles = page.locator('.tile:has(.popover)');
		await expect(tiles.first()).toBeVisible();
		const n = await tiles.count();
		let spilled = 0;
		for (let i = 0; i < n; i++) {
			const tile = tiles.nth(i);
			await tile.evaluate((el) => el.scrollIntoView({ block: 'center' }));
			await tile.locator('button.face').hover();
			const pop = tile.locator('.popover');
			const box = (await pop.boundingBox())!;
			const panelBottom = await tile.evaluate((el) => (el.closest('.panel') ?? el).getBoundingClientRect().bottom);
			if (box.y + box.height <= panelBottom) continue; // fully inside its own panel, nothing to cover it
			spilled++;
			const cx = box.x + box.width / 2;
			const cy = box.y + box.height - 3;
			await expect
				.poll(() => page.evaluate(([x, y]) => !!document.elementFromPoint(x, y)?.closest('.popover'), [cx, cy]))
				.toBe(true);
		}
		console.log(`${path}: ${n} tiles, ${spilled} spilled`);
	});
}
