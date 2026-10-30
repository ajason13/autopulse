import { readFile } from 'node:fs/promises';

const names = [
	'us-001-engine-data-contract.mdx',
	'us-002-virtual-replay-harness.mdx',
	'us-004-windowed-analysis.mdx',
	'us-006-ev-telemetry-data-contract.md',
];

export async function checkSpecs(
	canonicalDirectory = new URL('../../docs/specs/', import.meta.url),
	publishedDirectory = new URL('../src/content/docs/specs/', import.meta.url),
) {
	for (const name of names) {
		const canonical = await readFile(new URL(name, canonicalDirectory));
		const published = await readFile(new URL(name, publishedDirectory));
		if (!canonical.equals(published)) {
			throw new Error(`Spec publication drift: ${name}. Edit docs/specs/${name}, then copy it to grubby-galaxy/src/content/docs/specs/${name}.`);
		}
	}
}
