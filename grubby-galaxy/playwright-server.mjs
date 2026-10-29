const configuredPort = process.env.AUTOPULSE_DOCS_PORT ?? '4321';
export const port = Number(configuredPort);
if (!/^\d+$/.test(configuredPort) || !Number.isInteger(port) || port < 1 || port > 65535) {
	throw new Error('AUTOPULSE_DOCS_PORT must be an integer from 1 to 65535.');
}

export const baseURL = `http://127.0.0.1:${port}`;

/** @type {import('@playwright/test').TestConfig['webServer']} */
export const webServer = {
	command: 'node scripts/preview-docs.mjs',
	// Only our child can announce readiness after building and binding its port.
	// An HTTP readiness check alone could accept an unrelated stale server.
	wait: { stdout: /AutoPulse current-build preview ready/ },
	stdout: 'pipe',
	reuseExistingServer: false,
	timeout: 120_000,
	gracefulShutdown: { signal: 'SIGTERM', timeout: 5_000 },
};
