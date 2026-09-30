#!/usr/bin/env node
/**
 * Drops the dedicated end-to-end SQLite database before the Playwright `webServer` boots the stack.
 *
 * Determinism is the whole point (story E9-S4 AC-24): the committed screenshots only match when every
 * run starts from the same state — an empty database that `python -m src.seed` fills with the three
 * PUBLISHED v1 rule sets and the demo portfolio, plus whatever the specs create themselves. The file
 * name must stay in step with `POLICYFORGE_DATABASE_URL` in `e2e/playwright.config.ts`.
 */
import { existsSync, rmSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const BASE = join(ROOT, 'backend', 'policyforge-e2e.db');

// SQLite keeps the write-ahead log and shared-memory file beside the database; remove all three.
for (const path of [BASE, `${BASE}-wal`, `${BASE}-shm`]) {
  if (!existsSync(path)) continue;
  rmSync(path, { force: true });
  process.stdout.write(`[e2e] removed ${path}\n`);
}
process.stdout.write('[e2e] database reset — the stack will migrate and seed a fresh one\n');
