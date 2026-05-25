import { expect, test } from '@playwright/test';

const basePath = '/autopulse/';

const docsRoutes = [
	{ path: basePath, heading: 'AutoPulse' },
	{ path: `${basePath}guides/getting-started/`, heading: 'Getting Started' },
	{ path: `${basePath}guides/example/`, heading: 'Example Guide' },
	{ path: `${basePath}reference/anomaly-detection/`, heading: 'Anomaly Detection Reference' },
	{ path: `${basePath}reference/architecture/`, heading: 'Architecture Overview' },
	{ path: `${basePath}reference/empirical-validation/`, heading: 'Empirical Validation Report' },
	{ path: `${basePath}reference/example/`, heading: 'Example Reference' },
	{ path: `${basePath}specs/us-001-engine-data-contract/`, heading: 'US-001 Engine Data Contract' },
	{ path: `${basePath}specs/us-002-virtual-replay-harness/`, heading: 'US-002 Virtual Replay Harness' },
	{ path: `${basePath}specs/us-004-windowed-analysis/`, heading: 'US-004 Windowed Analysis (Smoothing)' },
	{ path: `${basePath}specs/us-006-ev-telemetry-data-contract/`, heading: 'US-006 EV Telemetry Data Contract' },
];

test.describe('Starlight route regression', () => {
	for (const route of docsRoutes) {
		test(`${route.path} renders expected documentation content`, async ({ page }) => {
			const response = await page.goto(route.path);

			expect(response?.status(), `${route.path} should not return an HTTP error`).toBeLessThan(400);
			await expect(page).toHaveTitle(/AutoPulse Docs/);
			await expect(page.getByRole('heading', { name: route.heading, level: 1, exact: true })).toBeVisible();
			await expect(page.getByRole('navigation', { name: 'Main' })).toContainText('Reference');
		});
	}
});

test('desktop sidebar exposes every primary documentation section', async ({ page }, testInfo) => {
	test.skip(!testInfo.project.name.includes('desktop'), 'Desktop sidebar check only runs on desktop.');

	await page.goto(`${basePath}reference/architecture/`);

	const mainNav = page.getByRole('navigation', { name: 'Main' });
	await expect(mainNav).toContainText('Guides');
	await expect(mainNav).toContainText('Specs');
	await expect(mainNav).toContainText('Reference');
	await expect(mainNav.getByRole('link', { name: 'US-006 EV Telemetry Data Contract' })).toBeVisible();
	await expect(mainNav.getByRole('link', { name: 'Architecture Overview' })).toBeVisible();
});

test('mobile sidebar opens from an interior docs page', async ({ page }, testInfo) => {
	test.skip(!testInfo.project.name.includes('mobile'), 'Mobile sidebar check only runs on mobile.');

	await page.goto(`${basePath}reference/architecture/`);
	await page.getByRole('button', { name: 'Menu' }).click();

	const mainNav = page.getByRole('navigation', { name: 'Main' });
	await expect(mainNav.getByRole('link', { name: 'Getting Started' })).toBeVisible();
	await expect(mainNav.getByRole('link', { name: 'US-001 Engine Data Contract' })).toBeVisible();
	await expect(mainNav.getByRole('link', { name: 'Empirical Validation' })).toBeVisible();
});

test('search dialog opens and accepts a query', async ({ page }) => {
	await page.goto(basePath);

	await page.getByRole('button', { name: 'Search' }).click();
	const dialog = page.getByRole('dialog');
	await expect(dialog).toBeVisible();
	const searchInput = dialog.locator('input').first();
	await searchInput.fill('US-006');
	await expect(searchInput).toHaveValue('US-006');
});

test.describe('Internal link base-path regression', () => {
	for (const route of docsRoutes) {
		test(`${route.path} internal links stay under /autopulse/ and resolve`, async ({ page }) => {
			await page.goto(route.path);

			const hrefs = await page
				.locator('main a[href]')
				.evaluateAll((anchors) =>
					anchors
						.map((anchor) => (anchor as HTMLAnchorElement).href)
						.filter((href) => href.startsWith(window.location.origin))
						.map((href) => new URL(href))
						.filter((url) => !url.hash || url.pathname !== window.location.pathname)
						.map((url) => `${url.pathname}${url.search}${url.hash}`)
				);

			const uniqueHrefs = [...new Set(hrefs)];

			for (const href of uniqueHrefs) {
				expect(href, `Internal link escaped the GitHub Pages base path on ${route.path}`).toMatch(
					/^\/autopulse\//
				);

				const response = await page.request.get(href);
				expect(response.status(), `${route.path} links to ${href}`).toBeLessThan(400);
			}
		});
	}
});
