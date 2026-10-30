import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readdir, readFile, writeFile, unlink, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { checkSpecs } from '../scripts/check-specs.mjs';

test('publication rejects drift and missing files for every public spec', async () => {
	const root = await mkdtemp(join(tmpdir(), 'autopulse-specs-'));
	try {
		const source = new URL('../../docs/specs/', import.meta.url);
		const canonical = pathToFileURL(`${root}/canonical/`);
		const published = pathToFileURL(`${root}/published/`);
		await mkdir(canonical);
		await mkdir(published);
		const names = (await readdir(source)).filter(name => name.startsWith('us-'));
		assert.equal(names.length, 4);
		for (const name of names) {
			const content = await readFile(new URL(name, source));
			await writeFile(new URL(name, canonical), content);
			await writeFile(new URL(name, published), content);
		}
		await checkSpecs(canonical, published);
		for (const name of names) {
			const content = await readFile(new URL(name, canonical));
			await writeFile(new URL(name, published), Buffer.concat([content, Buffer.from('\nStale copy\n')]));
			await assert.rejects(checkSpecs(canonical, published), /Spec publication drift/);
			await unlink(new URL(name, published));
			await assert.rejects(checkSpecs(canonical, published), /ENOENT/);
			await writeFile(new URL(name, published), content);
		}
		await checkSpecs(canonical, published);
	} finally {
		await rm(root, { recursive: true, force: true });
	}
});
