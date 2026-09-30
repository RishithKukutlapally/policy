#!/usr/bin/env node
/**
 * Cross-platform launcher for PolicyForge (`npm start`).
 *
 * Steps, in order:
 *   1. `uv sync` in backend/
 *   2. `uv run alembic upgrade head`
 *   3. `uv run python -m src.seed` (skipped when backend/src/seed.py does not exist yet)
 *   4. run the API on API_PORT and, if frontend/package.json exists, the Vite UI on UI_PORT
 *
 * Flags: --api-only | --ui-only | --migrate-only | --test
 * Works on Windows (uses shell:true and resolves uv from PATH or the default user install).
 */

import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const BACKEND = join(ROOT, "backend");
const FRONTEND = join(ROOT, "frontend");
const API_PORT = process.env.POLICYFORGE_API_PORT ?? process.env.API_PORT ?? "8000";
const UI_PORT = process.env.POLICYFORGE_UI_PORT ?? process.env.UI_PORT ?? "3000";
const args = new Set(process.argv.slice(2));

const log = (message) => process.stdout.write(`[policyforge] ${message}\n`);

/** Resolve the `uv` executable: PATH first, then the default per-user install locations. */
function resolveUv() {
  const probe = spawnSync("uv", ["--version"], { shell: true, stdio: "ignore" });
  if (probe.status === 0) return "uv";
  const home = process.env.USERPROFILE ?? process.env.HOME ?? "";
  const candidates = [
    join(home, "AppData", "Roaming", "Python", "Python313", "Scripts", "uv.exe"),
    join(home, "AppData", "Roaming", "Python", "Python312", "Scripts", "uv.exe"),
    join(home, ".local", "bin", "uv"),
    join(home, ".cargo", "bin", "uv"),
  ];
  const found = candidates.find((candidate) => existsSync(candidate));
  if (!found) {
    throw new Error("uv not found on PATH — install it from https://docs.astral.sh/uv/");
  }
  return `"${found}"`;
}

const UV = resolveUv();

/** Run a command to completion; exit the process on failure. */
function run(command, cwd, label) {
  log(`${label}: ${command}`);
  const result = spawnSync(command, { cwd, shell: true, stdio: "inherit" });
  if (result.status !== 0) {
    log(`${label} failed (exit ${result.status})`);
    process.exit(result.status ?? 1);
  }
}

/** Start a long-running child process and keep a handle for shutdown. */
function start(command, cwd, label) {
  log(`${label}: ${command}`);
  const child = spawn(command, { cwd, shell: true, stdio: "inherit" });
  child.on("exit", (code) => {
    log(`${label} exited with code ${code}`);
    shutdown(code ?? 0);
  });
  return child;
}

const children = [];
let shuttingDown = false;

function shutdown(code) {
  if (shuttingDown) return;
  shuttingDown = true;
  for (const child of children) {
    if (!child.killed) child.kill();
  }
  process.exit(code);
}

process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));

function installAndMigrate() {
  run(`${UV} sync`, BACKEND, "backend install");
  run(`${UV} run alembic upgrade head`, BACKEND, "migrate");
  if (existsSync(join(BACKEND, "src", "seed.py"))) {
    run(`${UV} run python -m src.seed`, BACKEND, "seed");
  } else {
    log("seed: skipped (backend/src/seed.py not present yet)");
  }
}

function startApi() {
  children.push(
    start(
      `${UV} run uvicorn src.main:app --host 127.0.0.1 --port ${API_PORT}`,
      BACKEND,
      `api :${API_PORT}`,
    ),
  );
}

function startUi() {
  if (!existsSync(join(FRONTEND, "package.json"))) {
    log("ui: skipped (frontend/package.json not present yet)");
    return;
  }
  if (!existsSync(join(FRONTEND, "node_modules"))) {
    run("npm install", FRONTEND, "ui install");
  }
  children.push(start(`npm run dev -- --port ${UI_PORT}`, FRONTEND, `ui :${UI_PORT}`));
}

if (args.has("--test")) {
  run(`${UV} sync`, BACKEND, "backend install");
  run(`${UV} run pytest -q`, BACKEND, "tests");
} else if (args.has("--migrate-only")) {
  installAndMigrate();
} else if (args.has("--ui-only")) {
  startUi();
} else if (args.has("--api-only")) {
  installAndMigrate();
  startApi();
} else {
  installAndMigrate();
  startApi();
  startUi();
}
