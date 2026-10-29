import { build, preview } from 'astro';
import { baseURL, port } from '../playwright-server.mjs';

// The API stays in this process; the Astro CLI can auto-background under agents.
await build({});
const server = await preview({
	server: { host: '127.0.0.1', port, open: false },
	vite: { preview: { strictPort: true } },
});
const closed = server.closed();
let stopping = false;
async function stop() {
	if (stopping) return;
	stopping = true;
	await server.stop();
}
process.once('SIGTERM', stop);
process.once('SIGINT', stop);
console.log(`AutoPulse current-build preview ready at ${baseURL}/autopulse/`);
await closed;
