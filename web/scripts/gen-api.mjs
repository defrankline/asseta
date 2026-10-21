// Generates src/api/generated/schema.ts from ../contracts/openapi.json using openapi-typescript.
// Tolerates the contract being absent (the backend exports it in Gate 0); exits 0 with a notice.
// Pass --strict to fail when the contract is missing (use in CI once the contract is committed).
import { existsSync, mkdirSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const webRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const input = resolve(webRoot, '..', 'contracts', 'openapi.json');
const output = resolve(webRoot, 'src', 'api', 'generated', 'schema.ts');
const strict = process.argv.includes('--strict');

if (!existsSync(input)) {
  const msg = `[gen:api] ${input} not found; skipping generation (hand-written DTOs in src/api/types.ts remain in use).`;
  if (strict) {
    console.error(msg);
    process.exit(1);
  }
  console.warn(msg);
  process.exit(0);
}

mkdirSync(dirname(output), { recursive: true });
const result = spawnSync('npx', ['--no-install', 'openapi-typescript', input, '-o', output], {
  cwd: webRoot,
  stdio: 'inherit',
});
process.exit(result.status ?? 1);
