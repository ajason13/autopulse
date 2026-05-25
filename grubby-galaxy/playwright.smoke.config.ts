import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
	testDir: './tests/smoke',
	timeout: 30_000,
	expect: {
		timeout: 5_000,
	},
	use: {
		baseURL: 'http://127.0.0.1:4321',
		trace: 'on-first-retry',
	},
	webServer: {
		command: 'npm run build && npm run preview -- --host 127.0.0.1',
		url: 'http://127.0.0.1:4321/autopulse/',
		reuseExistingServer: !process.env.CI,
		timeout: 120_000,
	},
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
