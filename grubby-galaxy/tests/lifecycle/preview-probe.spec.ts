import { expect, test } from '@playwright/test';

test('owned preview serves the current build', async ({ request }) => {
	const response = await request.get('/autopulse/');
	// The lifecycle harness deliberately fails this probe to test failure cleanup.
	expect(response.status()).toBe(process.env.AUTOPULSE_PROBE_FAIL === '1' ? 418 : 200);
	expect(await response.text()).toContain('AutoPulse');
});
