#!/usr/bin/env node
/**
 * grid-trading-skill installer — cross-platform Node CLI.
 *
 * Usage:
 *   npx grid-trading-skill                 # install both Claude + Codex
 *   npx grid-trading-skill install         # same as default
 *   npx grid-trading-skill install --claude-only
 *   npx grid-trading-skill install --codex-only
 *   npx grid-trading-skill uninstall
 *   npx grid-trading-skill status
 *   npx grid-trading-skill --help
 *
 * No external npm dependencies — uses Node stdlib only (Node 16+).
 */

'use strict';

const fs   = require('fs');
const os   = require('os');
const path = require('path');

// ---------------------------------------------------------------------------
// Package layout detection
// ---------------------------------------------------------------------------
const PKG_ROOT        = path.resolve(__dirname, '..');
const SRC_SKILL       = path.join(PKG_ROOT, 'grid_trading');
const SRC_AGENTS_MD   = path.join(PKG_ROOT, 'AGENTS.md');

const HOME            = os.homedir();
const CLAUDE_DIR      = path.join(HOME, '.claude', 'skills', 'grid-trading');
const CODEX_DIR       = path.join(HOME, '.codex', 'agents', 'grid-trading');

const VERSION         = require('../package.json').version;

// ---------------------------------------------------------------------------
// Pretty logging (no deps)
// ---------------------------------------------------------------------------
const C = {
  reset: '\x1b[0m', dim: '\x1b[2m', bold: '\x1b[1m',
  blue: '\x1b[34m', green: '\x1b[32m', yellow: '\x1b[33m', red: '\x1b[31m',
};
const supportsColor = process.stdout.isTTY && process.env.NO_COLOR === undefined;
const paint = (c, s) => supportsColor ? `${c}${s}${C.reset}` : s;

const info = (m) => console.log(`${paint(C.blue,   '[INFO]')} ${m}`);
const ok   = (m) => console.log(`${paint(C.green,  '[ OK ]')} ${m}`);
const warn = (m) => console.log(`${paint(C.yellow, '[WARN]')} ${m}`);
const err  = (m) => console.error(`${paint(C.red,  '[ERR ]')} ${m}`);

// ---------------------------------------------------------------------------
// Filesystem helpers (Node 16+ — uses fs.cpSync)
// ---------------------------------------------------------------------------
function copyTree(src, dst) {
  fs.mkdirSync(dst, { recursive: true });
  fs.cpSync(src, dst, {
    recursive: true,
    force: true,
    dereference: true,
    filter: (source) => {
      // Skip Python bytecode and test caches
      if (source.endsWith('__pycache__')) return false;
      if (source.endsWith('.pyc')) return false;
      return true;
    },
  });
}

function removeTree(target) {
  if (fs.existsSync(target)) {
    fs.rmSync(target, { recursive: true, force: true });
    return true;
  }
  return false;
}

function exists(p) {
  try { fs.accessSync(p); return true; } catch { return false; }
}

// ---------------------------------------------------------------------------
// Installer actions
// ---------------------------------------------------------------------------
function installClaude() {
  info(`Installing Claude Code skill → ${paint(C.dim, CLAUDE_DIR)}`);
  copyTree(SRC_SKILL, CLAUDE_DIR);
  ok('Claude Code skill installed');
  console.log(`     ${paint(C.dim, 'Open Claude Code and ask about "网格交易" or "grid trading"')}`);
}

function installCodex() {
  info(`Installing OpenAI Codex agent → ${paint(C.dim, CODEX_DIR)}`);
  copyTree(SRC_SKILL, CODEX_DIR);
  if (exists(SRC_AGENTS_MD)) {
    fs.copyFileSync(SRC_AGENTS_MD, path.join(CODEX_DIR, 'AGENTS.md'));
  }
  ok('Codex agent installed');
  console.log(`     ${paint(C.dim, 'In Codex CLI, reference: grid-trading')}`);
}

function uninstall() {
  const removedClaude = removeTree(CLAUDE_DIR);
  const removedCodex  = removeTree(CODEX_DIR);
  if (removedClaude) ok(`Removed ${CLAUDE_DIR}`);
  else               warn(`Not found: ${CLAUDE_DIR}`);
  if (removedCodex)  ok(`Removed ${CODEX_DIR}`);
  else               warn(`Not found: ${CODEX_DIR}`);
}

function status() {
  console.log(paint(C.bold, `\n  grid-trading-skill v${VERSION}\n`));
  console.log(`  ${exists(CLAUDE_DIR) ? paint(C.green, '✓') : paint(C.red, '✗')} Claude Code skill   ${paint(C.dim, CLAUDE_DIR)}`);
  console.log(`  ${exists(CODEX_DIR)  ? paint(C.green, '✓') : paint(C.red, '✗')} OpenAI Codex agent  ${paint(C.dim, CODEX_DIR)}`);
  console.log();
}

function install(flags) {
  // Heuristic for `postinstall` hook: skip when being installed as a
  // transitive dependency (node_modules deep path), not run by the user.
  if (flags.has('--silent-if-global-only')) {
    const insideNodeModules = PKG_ROOT.includes(path.sep + 'node_modules' + path.sep);
    const isGlobal = process.env.npm_config_global === 'true';
    if (insideNodeModules && !isGlobal) {
      // Being installed as a local dependency — don't touch user's home dir.
      return;
    }
  }

  console.log(paint(C.bold, `\n  grid-trading-skill v${VERSION} — installer\n`));

  const claudeOnly = flags.has('--claude-only');
  const codexOnly  = flags.has('--codex-only');

  if (!codexOnly) installClaude();
  if (!claudeOnly) installCodex();

  console.log();
  ok(paint(C.bold, 'Installation complete!'));
  console.log(`     ${paint(C.dim, 'Run "npx grid-trading-skill status" to verify.')}`);
  console.log();
}

function help() {
  console.log(`
  ${paint(C.bold, 'grid-trading-skill')} v${VERSION}
  ${paint(C.dim, 'Grid trading strategy — Claude Code & OpenAI Codex CLI skill.')}

  ${paint(C.bold, 'Usage:')}
    npx grid-trading-skill ${paint(C.dim, '[command] [options]')}

  ${paint(C.bold, 'Commands:')}
    install         Install skill into ~/.claude/ and ~/.codex/  ${paint(C.dim, '(default)')}
    uninstall       Remove both installations
    status          Show installation state
    help            Show this message

  ${paint(C.bold, 'Options (install):')}
    --claude-only   Install only Claude Code skill
    --codex-only    Install only Codex agent

  ${paint(C.bold, 'Examples:')}
    npx grid-trading-skill
    npx grid-trading-skill install --claude-only
    npx grid-trading-skill uninstall
`);
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
function main(argv) {
  const args  = argv.slice(2);
  const flags = new Set(args.filter((a) => a.startsWith('--')));
  let   cmd   = args.find((a) => !a.startsWith('--')) || 'install';
  if (flags.has('--help') || flags.has('-h') || args.includes('-h')) cmd = 'help';

  try {
    switch (cmd) {
      case 'install':            install(flags); break;
      case 'uninstall':          uninstall(); break;
      case 'status':             status(); break;
      case 'help':
      case '--help':
      case '-h':                 help(); break;
      default:
        err(`Unknown command: ${cmd}`);
        help();
        process.exit(1);
    }
  } catch (e) {
    err(e.message || String(e));
    if (process.env.DEBUG) console.error(e.stack);
    process.exit(1);
  }
}

main(process.argv);
