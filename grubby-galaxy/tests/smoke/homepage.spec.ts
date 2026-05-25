import { expect, test } from '@playwright/test';

const homePath = '/autopulse/';

test('homepage renders the AutoPulse documentation shell', async ({ page }) => {
	await page.goto(homePath);

	await expect(page).toHaveTitle(/AutoPulse/);
	await expect(page.getByRole('heading', { name: 'AutoPulse', level: 1 })).toBeVisible();
	await expect(page.getByRole('link', { name: 'Explore Specifications' })).toHaveAttribute(
		'href',
		'specs/us-001-engine-data-contract/'
	);
	await expect(page.getByRole('link', { name: 'View on GitHub' })).toHaveAttribute(
		'href',
		'https://github.com/ajason13/autopulse'
	);
});

test('homepage internal links resolve within the GitHub Pages base path', async ({ page }) => {
	await page.goto(homePath);

	const links = [
		page.getByRole('link', { name: 'Explore Specifications' }),
		page.getByRole('link', { name: 'US-001: Data Contract' }),
		page.getByRole('link', { name: 'US-006: EV Telemetry' }),
		page.getByRole('link', { name: 'Developer Setup' }),
	];

	for (const link of links) {
		const url = await link.evaluate((anchor) => new URL(anchor.href));

		expect(url.origin).toBe('http://127.0.0.1:4321');
		expect(url.pathname).toMatch(/^\/autopulse\//);
	}
});

test('mobile homepage exposes and opens the Starlight sidebar menu', async ({ page }, testInfo) => {
	test.skip(!testInfo.project.name.includes('mobile'), 'Mobile sidebar smoke check only runs on mobile.');

	await page.goto(homePath);

	const menuButton = page.getByRole('button', { name: 'Menu' });
	await expect(menuButton).toBeVisible();
	await menuButton.click();

	await expect(page.getByRole('navigation', { name: 'Main' })).toContainText('Guides');
	await expect(page.getByRole('navigation', { name: 'Main' })).toContainText('Specs');
	await expect(page.getByRole('navigation', { name: 'Main' })).toContainText('Reference');
	await expect(page.getByRole('link', { name: 'US-006 EV Telemetry Data Contract' })).toBeVisible();
});

test('desktop homepage shows the Starlight sidebar without opening a menu', async ({ page }, testInfo) => {
	test.skip(!testInfo.project.name.includes('desktop'), 'Desktop sidebar smoke check only runs on desktop.');

	await page.goto(homePath);

	await expect(page.getByRole('button', { name: 'Menu' })).toBeHidden();
	await expect(page.getByRole('navigation', { name: 'Main' })).toContainText('US-001 Engine Data Contract');
	await expect(page.getByRole('navigation', { name: 'On this page' })).toContainText(
		'Documentation Roadmap'
	);
});
