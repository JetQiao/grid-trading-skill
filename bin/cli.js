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

const fs            = require('fs');
const os            = require('os');
const path          = require('path');
const { spawnSync } = require('child_process');

// ---------------------------------------------------------------------------
// Package layout detection
// ---------------------------------------------------------------------------
const PKG_ROOT        = path.resolve(__dirname, '..');
const SRC_SKILL       = path.join(PKG_ROOT, 'grid_trading');
const SRC_AGENTS_MD   = path.join(PKG_ROOT, 'AGENTS.md');

const HOME            = os.homedir();
const CLAUDE_DIR      = path.join(HOME, '.claude', 'skills', 'grid-trading');
const CODEX_DIR       = path.join(HOME, '.codex', 'skills', 'grid-trading');
const CODEX_AGENTS_MD = path.join(HOME, '.codex', 'AGENTS.md');
const LEGACY_CODEX    = path.join(HOME, '.codex', 'agents', 'grid-trading');

const MARKER_BEGIN    = '<!-- BEGIN grid-trading-skill -->';
const MARKER_END      = '<!-- END grid-trading-skill -->';

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

function stripMarkerBlock(content) {
  const beginIdx = content.indexOf(MARKER_BEGIN);
  const endIdx   = content.indexOf(MARKER_END);
  if (beginIdx === -1 || endIdx === -1 || endIdx < beginIdx) return content;
  const before = content.slice(0, beginIdx).replace(/\n+$/, '');
  const after  = content.slice(endIdx + MARKER_END.length).replace(/^\n+/, '');
  return [before, after].filter(Boolean).join('\n\n');
}

function mergeIntoCodexAgentsFile() {
  if (!exists(SRC_AGENTS_MD)) return;
  const agentsBody = fs.readFileSync(SRC_AGENTS_MD, 'utf8').trim();
  fs.mkdirSync(path.dirname(CODEX_AGENTS_MD), { recursive: true });

  let existing = '';
  if (exists(CODEX_AGENTS_MD)) {
    existing = stripMarkerBlock(fs.readFileSync(CODEX_AGENTS_MD, 'utf8')).trim();
  }

  const block = `${MARKER_BEGIN}\n${agentsBody}\n${MARKER_END}`;
  const next  = existing ? `${existing}\n\n${block}\n` : `${block}\n`;
  fs.writeFileSync(CODEX_AGENTS_MD, next);
}

function unmergeFromCodexAgentsFile() {
  if (!exists(CODEX_AGENTS_MD)) return false;
  const original = fs.readFileSync(CODEX_AGENTS_MD, 'utf8');
  const stripped = stripMarkerBlock(original);
  if (stripped === original) return false;
  const trimmed = stripped.trim();
  if (trimmed) fs.writeFileSync(CODEX_AGENTS_MD, trimmed + '\n');
  else         fs.rmSync(CODEX_AGENTS_MD, { force: true });
  return true;
}

function installCodex() {
  info(`Installing Codex skill source → ${paint(C.dim, CODEX_DIR)}`);
  // Clean up legacy path from v1.1.0
  if (exists(LEGACY_CODEX)) {
    removeTree(LEGACY_CODEX);
    warn(`Removed legacy path: ${LEGACY_CODEX}`);
  }
  copyTree(SRC_SKILL, CODEX_DIR);
  ok('Codex skill source installed');

  info(`Merging directives into ${paint(C.dim, CODEX_AGENTS_MD)}`);
  mergeIntoCodexAgentsFile();
  ok('Codex AGENTS.md updated (marker block added/refreshed)');
  console.log(`     ${paint(C.dim, 'Codex will now invoke the Python package on grid-trading prompts.')}`);
}

function uninstall() {
  const removedClaude = removeTree(CLAUDE_DIR);
  const removedCodex  = removeTree(CODEX_DIR);
  const removedLegacy = removeTree(LEGACY_CODEX);
  const removedMerge  = unmergeFromCodexAgentsFile();

  if (removedClaude) ok(`Removed ${CLAUDE_DIR}`);
  else               warn(`Not found: ${CLAUDE_DIR}`);
  if (removedCodex)  ok(`Removed ${CODEX_DIR}`);
  else               warn(`Not found: ${CODEX_DIR}`);
  if (removedLegacy) ok(`Removed legacy ${LEGACY_CODEX}`);
  if (removedMerge)  ok(`Stripped marker block from ${CODEX_AGENTS_MD}`);
  else               warn(`No marker block in ${CODEX_AGENTS_MD}`);
}

function codexAgentsMerged() {
  if (!exists(CODEX_AGENTS_MD)) return false;
  return fs.readFileSync(CODEX_AGENTS_MD, 'utf8').includes(MARKER_BEGIN);
}

function status() {
  console.log(paint(C.bold, `\n  grid-trading-skill v${VERSION}\n`));
  console.log(`  ${exists(CLAUDE_DIR) ? paint(C.green, '✓') : paint(C.red, '✗')} Claude Code skill      ${paint(C.dim, CLAUDE_DIR)}`);
  console.log(`  ${exists(CODEX_DIR)  ? paint(C.green, '✓') : paint(C.red, '✗')} Codex skill source     ${paint(C.dim, CODEX_DIR)}`);
  console.log(`  ${codexAgentsMerged() ? paint(C.green, '✓') : paint(C.red, '✗')} Codex AGENTS.md block  ${paint(C.dim, CODEX_AGENTS_MD)}`);
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

// ---------------------------------------------------------------------------
// `run` — parse natural language → invoke Python CLI → open HTML
// ---------------------------------------------------------------------------
function findPython() {
  for (const candidate of ['python3', 'python']) {
    const r = spawnSync(candidate, ['--version'], { encoding: 'utf8' });
    if (r.status === 0) return candidate;
  }
  return null;
}

function parsePrompt(text) {
  // Normalize: lower-case Latin, replace fullwidth punctuation/digits, ~/到/-/—/到
  let s = text
    .replace(/[，、：；]/g, ',')
    .replace(/[～〜﹣–—]/g, '~')
    .replace(/到/g, '~')
    .replace(/[%％]/g, '%');
  const lower = s.toLowerCase();

  const parsed = {};

  // Symbol: BTC/USDT, ETH-USDT, SOLUSDT
  let m = s.match(/\b([A-Z]{2,10})\s*[\/\-]?\s*(USDT|USDC|USD|BTC|ETH)\b/i);
  if (m) parsed.symbol = `${m[1].toUpperCase()}/${m[2].toUpperCase()}`;

  // Range: "40000 ~ 60000", "40k-60k"
  m = s.match(/(\d[\d,\.]*)\s*[kK]?\s*~\s*(\d[\d,\.]*)\s*[kK]?/);
  if (m) {
    const toNum = (raw, ctx) => {
      const n = parseFloat(raw.replace(/,/g, ''));
      return /[kK]/.test(ctx) ? n * 1000 : n;
    };
    parsed.lower = toNum(m[1], m[0].split('~')[0]);
    parsed.upper = toNum(m[2], m[0].split('~')[1]);
  }

  // Grid count: "20 格" / "20 grids" / "20格"
  m = s.match(/(\d+)\s*(?:格|grids?|levels?)/i);
  if (m) parsed.count = parseInt(m[1], 10);

  // Capital: "本金 10000" / "10000 USDT 本金" / "capital 10000"
  m = s.match(/(?:本金|资金|capital)\D{0,4}(\d[\d,\.]*)/i)
   || s.match(/(\d[\d,\.]*)\s*(?:USDT|U)\s*(?:本金|资金)/i);
  if (m) parsed.capital = parseFloat(m[1].replace(/,/g, ''));

  // Fee rate: "0.1%" / "手续费 0.001"
  m = s.match(/(?:手续费|费率|fee)\D{0,4}(\d+(?:\.\d+)?)\s*(%)?/i)
   || s.match(/(\d+(?:\.\d+)?)\s*%\s*(?:手续费|费率|fee)/i);
  if (m) {
    let v = parseFloat(m[1]);
    if ((m[2] === '%') || (m[1].includes('.') === false && v >= 0.01)) v = v / 100;
    if (v > 0.5) v = v / 100; // sanity: 0.1 entered as "0.1%" without %
    parsed.fee = v;
  }

  // Grid type
  if (/等差|arithmetic/i.test(lower)) parsed.type = 'arithmetic';
  else if (/等比|geometric/i.test(lower)) parsed.type = 'geometric';

  return parsed;
}

function runReport(args) {
  const prompt = args.filter((a) => !a.startsWith('--')).slice(1).join(' ');
  const flags  = args.filter((a) => a.startsWith('--'));

  if (!prompt) {
    err('Usage: npx grid-trading-skill run "BTC/USDT 40000~60000 20格 本金10000 手续费0.1%" [--no-open] [--no-backtest] [--out path]');
    process.exit(1);
  }

  const parsed = parsePrompt(prompt);
  const missing = ['lower', 'upper', 'count', 'capital'].filter((k) => parsed[k] == null);
  if (missing.length) {
    err(`Could not parse: ${missing.join(', ')}. Got: ${JSON.stringify(parsed)}`);
    err('Try: npx grid-trading-skill run "BTC/USDT 40000~60000 20格 本金10000 手续费0.1%"');
    process.exit(1);
  }

  const py = findPython();
  if (!py) {
    err('Python 3.11+ is required but not found on PATH. Install Python first.');
    process.exit(1);
  }

  // Determine which copy of grid_trading to import. Prefer pip-installed; else
  // use the one we deployed to ~/.codex/skills/grid-trading or the package mirror.
  const env = { ...process.env };
  const candidates = [CODEX_DIR, CLAUDE_DIR, PKG_ROOT].filter(exists);
  env.PYTHONPATH = [...candidates, env.PYTHONPATH].filter(Boolean).join(path.delimiter);

  const noOpen = flags.includes('--no-open');
  const noBacktest = flags.includes('--no-backtest');
  let outIdx = flags.findIndex((f) => f.startsWith('--out'));
  let outPath = path.join(os.tmpdir(), `grid_report_${Date.now()}.html`);
  if (outIdx >= 0) {
    const f = flags[outIdx];
    if (f.includes('=')) outPath = f.split('=')[1];
    else if (args[args.indexOf(f) + 1]) outPath = args[args.indexOf(f) + 1];
  }

  const pyArgs = [
    '-m', 'grid_trading.cli',
    '--symbol',  parsed.symbol  || 'BTC/USDT',
    '--lower',   String(parsed.lower),
    '--upper',   String(parsed.upper),
    '--count',   String(parsed.count),
    '--capital', String(parsed.capital),
    '--fee',     String(parsed.fee != null ? parsed.fee : 0.001),
    '--type',    parsed.type || 'geometric',
    '--out',     outPath,
  ];
  if (!noBacktest) pyArgs.push('--backtest', 'sine');
  if (!noOpen)     pyArgs.push('--open');

  console.log(paint(C.bold, `\n  grid-trading-skill — generating report\n`));
  info(`Parsed:  ${JSON.stringify(parsed)}`);
  info(`Running: ${py} -m grid_trading.cli ...`);

  const r = spawnSync(py, pyArgs, { stdio: 'inherit', env });
  process.exit(r.status || 0);
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
    run "<prompt>"  Generate an HTML report from a natural-language prompt
    help            Show this message

  ${paint(C.bold, 'Options (install):')}
    --claude-only   Install only Claude Code skill
    --codex-only    Install only Codex agent

  ${paint(C.bold, 'Options (run):')}
    --no-open       Don't open the report in browser
    --no-backtest   Build grid only, skip backtest
    --out <path>    Output HTML path (default: tmp dir)

  ${paint(C.bold, 'Examples:')}
    npx grid-trading-skill
    npx grid-trading-skill install --claude-only
    npx grid-trading-skill run "BTC/USDT 40000~60000 20格 本金10000 手续费0.1%"
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
      case 'run':                runReport(args); break;
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
