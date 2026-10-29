import { defineConfig, devices } from '@playwright/test';
import { baseURL, webServer } from './playwright-server.mjs';

export default defineConfig({
	testDir: './tests/e2e',
	timeout: 45_000,
	expect: {
		timeout: 5_000,
	},
	use: {
		baseURL,
		trace: 'on-first-retry',
	},
	webServer,
	projects: [
		{
			name: 'desktop-chromium',
			use: {
				...devices['Desktop Chrome'],
				viewport: { width: 1280, height: 900 },
			},
		},
		{
			name: 'mobile-chromium',
			use: {
				...devices['Pixel 5'],
			},
		},
	],
});
