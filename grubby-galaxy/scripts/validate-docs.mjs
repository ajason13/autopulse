import { spawn } from 'node:child_process';
import { rm } from 'node:fs/promises';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { docsRoot, buildIdentity, recordBuild, verifyBuild, productionConfig, provenanceFile } from './docs-provenance.mjs';

function npm(args, env = {}) {
	if (!process.env.npm_execpath) throw new Error('Use npm run validate:docs');
	return new Promise((accept, reject) => {
		const child = spawn(process.execPath, [process.env.npm_execpath, ...args], {
			cwd: docsRoot, env: { ...process.env, AUTOPULSE_DOCS_PREBUILT: '', ...env }, stdio: 'inherit',
		});
		child.once('error', reject);
		child.once('close', (code, signal) => code === 0 && !signal ? accept() : reject(new Error(`npm ${args.join(' ')} failed (${signal ?? code})`)));
	});
}

// Dependency installation stays an explicit workflow step. Everything after
// it is shared by CI and Pages, and stops at the first failure/cancellation.
export async function validateDocs({ run = npm, build, identity = buildIdentity, record = expected => recordBuild(docsRoot, process.env, expected), verify = verifyBuild, invalidate = () => rm(resolve(docsRoot, 'dist', provenanceFile), { force: true }) } = {}) {
	await invalidate();
	try {
		await run(['audit', '--omit=dev', '--audit-level=high']);
		await run(['exec', '--', 'playwright', 'install', '--with-deps', 'chromium']);
		await run(['run', 'test:specs']);
		await run(['run', 'test:provenance']);
		await run(['run', 'build']); // lifecycle probes deliberately overwrite dist
		await run(['run', 'test:lifecycle']);
		const inputs = await identity();
		await (build ?? (async () => (await import('astro')).build(productionConfig)))();
		await record(inputs);
		await run(['run', 'test:smoke'], { AUTOPULSE_DOCS_PREBUILT: '1' });
		await verify();
		await run(['run', 'test:e2e'], { AUTOPULSE_DOCS_PREBUILT: '1' });
		const result = await verify();
		const { files, ...summary } = result;
		console.log(`Validated docs artifact: ${JSON.stringify(summary)}`);
		return result;
	} catch (error) {
		await invalidate(); // a failed suite cannot leave a usable prebuilt receipt
		throw error;
	}
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
	await validateDocs();
}
