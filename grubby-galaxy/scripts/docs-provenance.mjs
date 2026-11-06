import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { lstat, readdir, readFile, writeFile } from 'node:fs/promises';
import { resolve, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

export const docsRoot = fileURLToPath(new URL('../', import.meta.url));
export const productionConfig = { site: 'https://ajason13.github.io', base: '/autopulse/' };
export const provenanceFile = 'autopulse-build.json';
const hash = data => createHash('sha256').update(data).digest('hex');

// No links or special files: upload-pages-artifact dereferences links, which
// could otherwise upload bytes different from those inspected here.
async function filesUnder(root, directory = '') {
	const result = [];
	for (const name of (await readdir(resolve(root, directory))).sort()) {
		assert(!['.git', '.github'].includes(name), `Entry excluded by Pages upload: ${name}`);
		const path = directory ? `${directory}/${name}` : name;
		const stat = await lstat(resolve(root, path));
		if (stat.isDirectory()) result.push(...await filesUnder(root, path));
		else {
			assert(stat.isFile() && !stat.isSymbolicLink(), `Unsupported artifact entry: ${path}`);
			if (path !== provenanceFile) result.push([path, hash(await readFile(resolve(root, path)))]);
		}
	}
	return result;
}

export async function buildIdentity(root = docsRoot, env = process.env) {
	const repo = execFileSync('git', ['rev-parse', '--show-toplevel'], { cwd: root, encoding: 'utf8' }).trim();
	const sha = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim();
	assert(!env.GITHUB_SHA || env.GITHUB_SHA === sha, 'Checkout does not match GITHUB_SHA');
	const prefix = relative(repo, root).replaceAll('\\', '/');
	const names = execFileSync('git', ['ls-files', '-z', '--cached', '--others', '--exclude-standard', '--', prefix, 'docs/specs'], { cwd: repo }).toString().split('\0').filter(Boolean).sort();
	const source = await Promise.all(names.map(async path => [path, hash(await readFile(resolve(repo, path)))]));
	return {
		version: 1, sha, run: env.GITHUB_RUN_ID ?? 'local', attempt: env.GITHUB_RUN_ATTEMPT ?? 'local',
		config: productionConfig,
		lock: hash(await readFile(resolve(root, 'package-lock.json'))),
		source: hash(JSON.stringify(source)),
	};
}

export async function recordBuild(root = docsRoot, env = process.env, expectedIdentity) {
	const identity = await buildIdentity(root, env);
	if (expectedIdentity) assert.deepEqual(identity, expectedIdentity, 'Build inputs changed during build');
	const files = await filesUnder(resolve(root, 'dist'));
	assert(files.some(([name]) => name === 'index.html'), 'Missing built homepage');
	const record = { ...identity, files, digest: hash(JSON.stringify(files)) };
	await writeFile(resolve(root, 'dist', provenanceFile), `${JSON.stringify(record, null, 2)}\n`);
	return record;
}

export async function verifyBuild(root = docsRoot, env = process.env) {
	const record = JSON.parse(await readFile(resolve(root, 'dist', provenanceFile), 'utf8'));
	const identity = await buildIdentity(root, env);
	for (const [key, value] of Object.entries(identity)) {
		assert.deepEqual(record[key], value, `Stale build provenance: ${key}`);
	}
	const files = await filesUnder(resolve(root, 'dist'));
	assert.deepEqual(record.files, files, 'Built artifact changed after validation');
	assert.equal(record.digest, hash(JSON.stringify(files)), 'Artifact digest mismatch');
	return record;
}
