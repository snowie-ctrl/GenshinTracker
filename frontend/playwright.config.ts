import { defineConfig } from '@playwright/test';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const PORT = 8799;
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const python = process.env.PYTHON ?? 'python';

export default defineConfig({
	testDir: 'e2e',
	// Every spec shares one stateful server; a spec's brief change (e.g. a member raised to Build) must not
	// race another spec's assertions, so files run one at a time.
	workers: 1,
	use: { baseURL: `http://127.0.0.1:${PORT}` },
	webServer: {
		// Fresh fake data every run; offline so no network or HoYoLAB is touched.
		command: `${python} -m app.devseed --root "${resolve(root, '.e2e-data')}" && ${python} "${resolve(root, 'run.py')}" --no-build`,
		cwd: resolve(root, 'backend'),
		url: `http://127.0.0.1:${PORT}/api/health`,
		reuseExistingServer: false,
		timeout: 60_000,
		env: { GT_ROOT: resolve(root, '.e2e-data'), GT_OFFLINE: '1', PORT: String(PORT) }
	}
});
