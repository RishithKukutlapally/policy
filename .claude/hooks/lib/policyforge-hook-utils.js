'use strict';

// Shared helpers for PolicyForge project hooks (PreToolUse on Write|Edit|MultiEdit).
// Hooks read the tool call from stdin (fd 0 — portable across Windows/Linux/macOS),
// compute the content the file WOULD have after the tool runs, and block with exit 2
// + a stderr reason (the channel Claude Code feeds back to the model).

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

let lastInput = null;

function readInput() {
  try {
    lastInput = JSON.parse(fs.readFileSync(0, 'utf8'));
  } catch (_) {
    lastInput = null;
  }
  return lastInput;
}

function normalize(filePath) {
  return String(filePath || '').replace(/\\/g, '/');
}

function readCurrent(filePath) {
  try {
    return fs.readFileSync(filePath, 'utf8');
  } catch (_) {
    return null;
  }
}

function applyEdit(content, oldStr, newStr, replaceAll) {
  if (content === null) return null;
  if (replaceAll) return content.split(oldStr).join(newStr);
  const idx = content.indexOf(oldStr);
  if (idx === -1) return null;
  return content.slice(0, idx) + newStr + content.slice(idx + oldStr.length);
}

// Returns the proposed full file content, or null when it cannot be determined.
function proposedContent(input) {
  const ti = input.tool_input || {};
  const current = readCurrent(ti.file_path);
  switch (input.tool_name) {
    case 'Write':
      return ti.content || '';
    case 'Edit':
      return applyEdit(current, ti.old_string || '', ti.new_string || '', Boolean(ti.replace_all));
    case 'MultiEdit': {
      let content = current;
      for (const e of ti.edits || []) {
        content = applyEdit(content, e.old_string || '', e.new_string || '', Boolean(e.replace_all));
      }
      return content;
    }
    default:
      return null;
  }
}

// Project root: CLAUDE_PROJECT_DIR (set by Claude Code, also when installed as a plugin), then the
// hook payload's cwd, then the nearest ancestor of this script that contains .claude/.
function findProjectDir() {
  if (process.env.CLAUDE_PROJECT_DIR) return path.resolve(process.env.CLAUDE_PROJECT_DIR);
  if (lastInput && lastInput.cwd && fs.existsSync(path.join(lastInput.cwd, '.claude'))) {
    return path.resolve(lastInput.cwd);
  }
  let cur = path.dirname(path.resolve(__filename));
  while (true) {
    if (fs.existsSync(path.join(cur, '.claude'))) return cur;
    const parent = path.dirname(cur);
    if (parent === cur) return process.cwd();
    cur = parent;
  }
}

// Path relative to the project root, forward slashes ('' if outside the project).
// NTFS / APFS are case-insensitive, so on those hosts the result is lower-cased: `Backend/src/x.py`
// and `backend/src/x.py` are the same file and must hit the same rules.
function relativeToProject(filePath) {
  const caseInsensitive = process.platform === 'win32' || process.platform === 'darwin';
  const root = path.resolve(findProjectDir());
  const target = path.resolve(root, filePath);
  let rel = path.relative(caseInsensitive ? root.toLowerCase() : root, caseInsensitive ? target.toLowerCase() : target);
  if (rel.startsWith('..') || path.isAbsolute(rel)) return '';
  rel = normalize(rel);
  return caseInsensitive ? rel.toLowerCase() : rel;
}

let trackedIndex = null;

// Map of lower-cased tracked path -> real tracked path (git paths are case-sensitive, NTFS is not).
function trackedPaths() {
  if (trackedIndex === null) {
    const r = spawnSync('git', ['ls-files', '-z'], { cwd: findProjectDir(), encoding: 'utf8' });
    trackedIndex = new Map();
    if (r.status === 0) for (const p of r.stdout.split('\0')) if (p) trackedIndex.set(p.toLowerCase(), p);
  }
  return trackedIndex;
}

// Content of a file at git HEAD, or null if the file is not committed. The lookup is
// case-insensitive so `Backend/.../0001_Init.py` still resolves to the committed file.
function committedContent(relPath) {
  const real = trackedPaths().get(relPath.toLowerCase()) || relPath;
  const r = spawnSync('git', ['show', `HEAD:${real}`], { cwd: findProjectDir(), encoding: 'utf8' });
  return r.status === 0 ? r.stdout : null;
}

// Index of the first '#' that starts a Python comment (i.e. not inside a string literal), or -1.
function commentStart(line) {
  let quote = null;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (quote) {
      if (ch === '\\') i++;
      else if (ch === quote) quote = null;
    } else if (ch === '"' || ch === "'") {
      quote = ch;
    } else if (ch === '#') {
      return i;
    }
  }
  return -1;
}

// Strip Python comments so rules only match real code ('#' inside strings is kept).
function codeLines(content) {
  return content.split('\n').map((line, i) => {
    const hash = commentStart(line);
    const code = hash === -1 ? line : line.slice(0, hash);
    return { n: i + 1, code, raw: line };
  });
}

function block(hookName, filePath, findings, fix) {
  const lines = [`BLOCKED by ${hookName}: ${filePath}`];
  for (const f of findings) lines.push(`  ${f}`);
  lines.push(`Fix: ${fix}`);
  process.stderr.write(lines.join('\n') + '\n');
  process.exit(2);
}

module.exports = {
  readInput,
  normalize,
  proposedContent,
  relativeToProject,
  committedContent,
  codeLines,
  block,
};
