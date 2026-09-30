#!/usr/bin/env node
'use strict';

// NFR-02 / NFR-05 guard: published policy rule versions and committed migrations are append-only.
//  - backend/policy_rules/<product>/v<N>.json: once committed with "status": "PUBLISHED",
//    the file may never change. Publish a new version file (v<N+1>.json) instead.
//  - backend/migrations/versions/*.py: once committed, a migration may never change.
//    Add a new migration instead.
// Uncommitted DRAFT rule files and uncommitted migrations can still be iterated on.

const u = require('./lib/policyforge-hook-utils');

const RULE_FILE = /^backend\/policy_rules\/[a-z_]+\/v\d+\.json$/i;
const MIGRATION = /^backend\/migrations\/versions\/[^/]+\.py$/i;
const LEDGER = /^backend\/policy_rules\/published\.lock$/i;

function isPublished(json) {
  try {
    return String(JSON.parse(json).status).toUpperCase() === 'PUBLISHED';
  } catch (_) {
    return /"status"\s*:\s*"PUBLISHED"/i.test(json);
  }
}

const input = u.readInput();
if (!input) process.exit(0);
const filePath = (input.tool_input && input.tool_input.file_path) || '';
const rel = u.relativeToProject(filePath);
if (!rel) process.exit(0);

if (RULE_FILE.test(rel)) {
  const committed = u.committedContent(rel);
  if (committed !== null && isPublished(committed)) {
    const proposed = u.proposedContent(input);
    if (proposed === null || proposed !== committed) {
      u.block(
        'policy-immutability-check (NFR-02)',
        rel,
        ['This rule-set version is PUBLISHED at HEAD — published versions are immutable.'],
        'Create the next version file (run /publish-policy-version <product>) and change that DRAFT instead.'
      );
    }
  }
}

// PUBLISHED.lock is an append-only ledger: every committed line must survive, in order, at the top.
if (LEDGER.test(rel)) {
  const committed = u.committedContent('backend/policy_rules/PUBLISHED.lock');
  const proposed = u.proposedContent(input);
  if (committed !== null && (proposed === null || !proposed.replace(/\r\n/g, '\n').startsWith(committed.replace(/\r\n/g, '\n')))) {
    u.block(
      'policy-immutability-check (NFR-02)',
      rel,
      ['PUBLISHED.lock is append-only — existing ledger lines may not be changed, removed or reordered.'],
      'Only append a new "<sha256>  <path>" line when publishing a version (/publish-policy-version).'
    );
  }
}

if (MIGRATION.test(rel) && u.committedContent(rel) !== null) {
  u.block(
    'policy-immutability-check (NFR-05)',
    rel,
    ['This migration is already committed — migrations are append-only.'],
    'Generate a new Alembic revision (uv run alembic revision -m "...") that alters the schema forward.'
  );
}

process.exit(0);
