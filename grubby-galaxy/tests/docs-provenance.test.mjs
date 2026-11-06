import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import { buildIdentity, recordBuild, verifyBuild, provenanceFile } from '../scripts/docs-provenance.mjs';
import { validateDocs } from '../scripts/validate-docs.mjs';

test('prebuilt provenance rejects missing, stale, changed and foreign output', async t => {
	const repo = await mkdtemp(join(tmpdir(), 'autopulse provenance '));
	t.after(() => rm(repo, { recursive: true, force: true }));
	const root = join(repo, 'site');
	await mkdir(join(root, 'dist'), { recursive: true });
	await writeFile(join(root, 'package-lock.json'), '{}');
	await writeFile(join(root, '.gitignore'), 'dist/\n');
	await writeFile(join(root, 'astro.config.mjs'), 'original config');
	execFileSync('git', ['init', '-q', repo]);
	execFileSync('git', ['-C', repo, 'add', '.']);
	execFileSync('git', ['-C', repo, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'fixture']);
	const env = { GITHUB_RUN_ID: '123', GITHUB_RUN_ATTEMPT: '1' };
	await assert.rejects(verifyBuild(root, env));
	await assert.rejects(recordBuild(root, env), /Missing built homepage/);
	await writeFile(join(root, 'dist', 'index.html'), 'current homepage');
	const original = await recordBuild(root, env);
	await assert.rejects(recordBuild(root, env, { ...await buildIdentity(root, env), source: 'stale' }), /inputs changed/);
	assert.deepEqual(await verifyBuild(root, env), original);
	await assert.rejects(verifyBuild(root, { ...env, GITHUB_RUN_ID: '456' }), /provenance: run/);
	await assert.rejects(verifyBuild(root, { ...env, GITHUB_RUN_ATTEMPT: '2' }), /provenance: attempt/);
	await assert.rejects(buildIdentity(root, { ...env, GITHUB_SHA: '0'.repeat(40) }), /Checkout does not match/);
	for (const key of ['sha', 'config', 'digest']) {
		await writeFile(join(root, 'dist', provenanceFile), JSON.stringify({ ...original, [key]: 'wrong' }));
		await assert.rejects(verifyBuild(root, env));
	}
	await writeFile(join(root, 'dist', provenanceFile), JSON.stringify(original));
	for (const name of ['index.html', 'unexpected.txt']) {
		await writeFile(join(root, 'dist', name), 'tampered');
		await assert.rejects(verifyBuild(root, env), /artifact changed/);
		if (name === 'index.html') await writeFile(join(root, 'dist', name), 'current homepage');
		else await rm(join(root, 'dist', name));
	}
	for (const name of ['package-lock.json', 'astro.config.mjs']) {
		const path = join(root, name);
		const bytes = await readFile(path);
		await writeFile(path, 'modified input');
		await assert.rejects(verifyBuild(root, env), /provenance/);
		await writeFile(path, bytes);
	}
	await rm(join(root, 'dist', 'index.html'));
	await assert.rejects(verifyBuild(root, env), /artifact changed/);
});

function harness(failAt = -1) {
	const events = [];
	let step = 0;
	const call = async label => {
		events.push(label);
		if (step++ === failAt) throw new Error(`controlled failure: ${label}`);
		return { digest: 'fixture' };
	};
	return { events, options: {
		run: (args, env) => call([args.join(' '), env?.AUTOPULSE_DOCS_PREBUILT]),
		identity: () => call('identity'), build: () => call('final build'), record: () => call('record'), verify: () => call('verify'),
		invalidate: async () => events.push('invalidate'),
	} };
}

test('shared validation stops at every failed gate and invalidates prebuilt receipt', async () => {
	const success = harness();
	await validateDocs(success.options);
	assert.deepEqual(success.events, [
		'invalidate', ['audit --omit=dev --audit-level=high', undefined],
		['exec -- playwright install --with-deps chromium', undefined],
		['run test:specs', undefined], ['run test:provenance', undefined],
		['run build', undefined], ['run test:lifecycle', undefined],
		'identity', 'final build', 'record', ['run test:smoke', '1'], 'verify', ['run test:e2e', '1'], 'verify',
	]);
	for (let index = 0; index < success.events.length - 1; index++) {
		const failure = harness(index);
		await assert.rejects(validateDocs(failure.options), /controlled failure/);
		assert.deepEqual(failure.events, [...success.events.slice(0, index + 2), 'invalidate']);
	}
});
