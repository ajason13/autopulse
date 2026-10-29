import { defineConfig } from '@playwright/test';
import { baseURL, webServer } from './playwright-server.mjs';

export default defineConfig({
	testDir: './tests/lifecycle',
	testMatch: 'preview-probe.spec.ts',
	use: { baseURL },
	webServer,
	workers: 1,
});
