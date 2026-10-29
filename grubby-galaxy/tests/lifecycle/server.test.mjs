import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { writeFile } from 'node:fs/promises';
import { createServer } from 'node:http';
import { createServer as createSocket } from 'node:net';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../../', import.meta.url));

async function listen(server, port = 0) {
	server.listen(port, '127.0.0.1');
	await once(server, 'listening');
	return server.address().port;
}

function close(server) {
	return new Promise((resolve, reject) => server.close(error => error ? reject(error) : resolve()));
}

async function runProbe(port, fail = false) {
	const child = spawn(process.execPath, [
		'node_modules/@playwright/test/cli.js', 'test', '--config', 'playwright.lifecycle.config.ts',
	], {
		cwd: root,
		env: { ...process.env, AUTOPULSE_DOCS_PORT: String(port), AUTOPULSE_PROBE_FAIL: fail ? '1' : '0' },
		stdio: ['ignore', 'pipe', 'pipe'],
		timeout: 150_000,
	});
	let output = '';
	child.stdout.on('data', chunk => output += chunk);
	child.stderr.on('data', chunk => output += chunk);
	const [code, signal] = await once(child, 'close');
	assert.equal(signal, null, output);
	return { code, output };
}

test('browser verification owns its server and rebuilds before readiness', { timeout: 660_000 }, async t => {
	for (const status of [200, 404]) {
		await t.test(`rejects a stale HTTP ${status} server and leaves it alive`, async () => {
			const stale = createServer((_req, res) => res.writeHead(status).end('stale docs'));
			const port = await listen(stale);
			try {
				const result = await runProbe(port);
				assert.notEqual(result.code, 0, result.output);
				assert.match(result.output, /Port \d+ is already in use/);
				assert.doesNotMatch(result.output, /AutoPulse current-build preview ready/);
				assert.equal(await (await fetch(`http://127.0.0.1:${port}/autopulse/`)).text(), 'stale docs');
			} finally {
				await close(stale);
			}
		});
	}

	for (const fail of [false, true]) {
		await t.test(`rebuilds stale output and releases its port after ${fail ? 'failure' : 'success'}`, async () => {
			const socket = createSocket();
			const port = await listen(socket);
			await close(socket);
			await writeFile(new URL('../../dist/index.html', import.meta.url), 'obsolete build');
			const result = await runProbe(port, fail);
			assert.equal(result.code, fail ? 1 : 0, result.output);
			assert.match(result.output, /AutoPulse current-build preview ready/);
			assert.match(result.output, fail ? /1 failed/ : /1 passed/);
			// Rebinding proves no owned listener remains after Playwright teardown.
			await listen(socket, port);
			await close(socket);
		});
	}
});
