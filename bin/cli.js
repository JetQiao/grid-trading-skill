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
const readline      = require('readline');
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

// ---------------------------------------------------------------------------
// `auto <symbol> [capital]` — easiest path: one symbol + one number → report
// ---------------------------------------------------------------------------
function buildAutoArgs(symbol, capital, opts) {
  const outPath = opts.out || path.join(os.tmpdir(), `grid_report_${Date.now()}.html`);
  const args = [
    '-m', 'grid_trading.cli',
    '--auto',     symbol,
    '--capital',  String(capital),
    '--out',      outPath,
  ];
  if (opts.fee != null) args.push('--fee', String(opts.fee));
  if (opts.method)      args.push('--method', opts.method);
  if (opts.window)      args.push('--window', String(opts.window));
  if (opts.safety)      args.push('--safety', String(opts.safety));
  if (opts.maxGrids)    args.push('--max-grids', String(opts.maxGrids));
  if (opts.backtest)    args.push('--backtest', opts.backtest);
  if (!opts.noOpen)     args.push('--open');
  return { args, outPath };
}

function pythonEnv() {
  const env = { ...process.env };
  const candidates = [CODEX_DIR, CLAUDE_DIR, PKG_ROOT].filter(exists);
  env.PYTHONPATH = [...candidates, env.PYTHONPATH].filter(Boolean).join(path.delimiter);
  return env;
}

function runAuto(argv) {
  const positional = argv.filter((a) => !a.startsWith('--'));
  const flags = argv.filter((a) => a.startsWith('--'));
  const symbol  = positional[1];
  const capital = positional[2] ? parseFloat(String(positional[2]).replace(/[万w]/i, '0000').replace(/,/g, '')) : 10000;

  if (!symbol) {
    err('用法: npx grid-trading-skill auto <代码> [本金]');
    err('示例: npx grid-trading-skill auto 600519 50000');
    err('     npx grid-trading-skill auto BTC/USDT 10000');
    err('     npx grid-trading-skill auto AAPL 5000');
    err('如不知道写什么，请运行 npx grid-trading-skill ask 进入向导。');
    process.exit(1);
  }
  if (!Number.isFinite(capital) || capital <= 0) {
    err(`本金解析失败: ${positional[2]}`);
    process.exit(1);
  }

  const py = findPython();
  if (!py) {
    err('需要 Python 3.11+，但 PATH 上没找到。请先安装 Python。');
    process.exit(1);
  }

  const opts = {
    fee:       getFlagValue(flags, '--fee', argv),
    method:    getFlagValue(flags, '--method', argv),
    window:    getFlagValue(flags, '--window', argv),
    safety:    getFlagValue(flags, '--safety', argv),
    maxGrids:  getFlagValue(flags, '--max-grids', argv),
    backtest:  flags.includes('--backtest') ? 'auto' : null,
    noOpen:    flags.includes('--no-open'),
  };

  const { args: pyArgs } = buildAutoArgs(symbol, capital, opts);

  console.log(paint(C.bold, `\n  grid-trading-skill v${VERSION} — auto mode\n`));
  info(`代码:   ${symbol}`);
  info(`本金:   ${capital.toLocaleString()}`);
  info('正在拉取实时数据 + 计算建议...');

  const r = spawnSync(py, pyArgs, { stdio: 'inherit', env: pythonEnv() });
  if (r.status !== 0) {
    err('生成失败。常见原因：');
    err('  · 网络无法访问东方财富 / Yahoo / Binance（请检查代理）');
    err('  · 代码格式错误（A 股 600519 / 港股 00700 / 美股 AAPL / 加密 BTC/USDT）');
    process.exit(r.status || 1);
  }
}

function getFlagValue(flags, name, argv) {
  const f = flags.find((x) => x === name || x.startsWith(name + '='));
  if (!f) return null;
  if (f.includes('=')) return f.split('=').slice(1).join('=');
  const idx = argv.indexOf(name);
  return idx >= 0 ? argv[idx + 1] : null;
}

// ---------------------------------------------------------------------------
// `ask` — interactive wizard for total beginners
// ---------------------------------------------------------------------------
async function ask() {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  const q  = (prompt) => new Promise((resolve) => rl.question(prompt, resolve));

  console.log(paint(C.bold, `\n  grid-trading-skill v${VERSION} — 网格交易向导\n`));
  console.log(paint(C.dim, '  按回车使用默认值，Ctrl+C 退出。\n'));

  let symbol = (await q(paint(C.blue, '? ') + '股票代码 (A股=600519, 港股=00700, 美股=AAPL, 加密=BTC/USDT): ')).trim();
  while (!symbol) {
    symbol = (await q(paint(C.yellow, '! ') + '必填，请输入: ')).trim();
  }

  const capRaw = (await q(paint(C.blue, '? ') + '本金 (默认 10000，可写 5万 或 50000): ')).trim();
  let capital = 10000;
  if (capRaw) {
    const norm = capRaw.replace(/万/g, '0000').replace(/,/g, '');
    const n = parseFloat(norm);
    if (Number.isFinite(n) && n > 0) capital = n;
    else { err(`本金无效: ${capRaw}`); rl.close(); process.exit(1); }
  }

  const feeRaw = (await q(paint(C.blue, '? ') + '手续费率 (默认 0.001 = 0.1%，A 股可写 0.0003): ')).trim();
  const fee = feeRaw ? parseFloat(feeRaw) : null;

  const methodRaw = (await q(paint(C.blue, '? ') + '上下限算法 [sigma/atr/quantile] (默认 sigma): ')).trim().toLowerCase();
  const method = ['sigma', 'atr', 'quantile'].includes(methodRaw) ? methodRaw : null;

  const btRaw = (await q(paint(C.blue, '? ') + '是否用真实历史回测一次？[Y/n] (默认 Y): ')).trim().toLowerCase();
  const backtest = (btRaw === '' || btRaw === 'y' || btRaw === 'yes') ? 'auto' : null;

  const openRaw = (await q(paint(C.blue, '? ') + '生成后用浏览器打开？[Y/n] (默认 Y): ')).trim().toLowerCase();
  const noOpen = openRaw === 'n' || openRaw === 'no';

  rl.close();

  const py = findPython();
  if (!py) { err('需要 Python 3.11+，请先安装 Python。'); process.exit(1); }

  const { args: pyArgs } = buildAutoArgs(symbol, capital, { fee, method, backtest, noOpen });

  console.log();
  info(`正在为 ${paint(C.bold, symbol)} 生成网格建议（本金 ${capital.toLocaleString()}）...`);
  const r = spawnSync(py, pyArgs, { stdio: 'inherit', env: pythonEnv() });
  if (r.status !== 0) {
    err('生成失败。可能是网络问题（无法访问东方财富/Yahoo/Binance）或代码格式错误。');
    process.exit(r.status || 1);
  }
}

function help() {
  console.log(`
  ${paint(C.bold, 'grid-trading-skill')} v${VERSION}
  ${paint(C.dim, 'Grid trading strategy — Claude Code & OpenAI Codex CLI skill.')}

  ${paint(C.bold, '零代码三种最快用法:')}
    ${paint(C.green, '①')} 交互式向导:        npx grid-trading-skill ask
    ${paint(C.green, '②')} 一行 auto 命令:    npx grid-trading-skill auto 600519 50000
    ${paint(C.green, '③')} 装到 Claude Code:  npx grid-trading-skill   ${paint(C.dim, '(默认 install)')}
                          然后在 Claude Code 里用大白话说"帮我看茅台 5 万本金网格"

  ${paint(C.bold, 'Usage:')}
    npx grid-trading-skill ${paint(C.dim, '[command] [options]')}

  ${paint(C.bold, 'Commands:')}
    install                         安装到 ~/.claude/ 和 ~/.codex/  ${paint(C.dim, '(默认)')}
    uninstall                       卸载
    status                          查看安装状态
    auto <代码> [本金]              一行命令出真实数据网格报告  ${paint(C.green, '★ v1.2.1 推荐')}
    ask                             交互式向导，问答式生成报告  ${paint(C.green, '★ 零代码')}
    run "<自然语言>"                解析中文 prompt 并生成报告（手动模式）
    help                            显示帮助

  ${paint(C.bold, 'auto / ask 选项:')}
    --no-open                       不要自动打开浏览器
    --backtest                      额外跑一次真实历史回测
    --fee 0.0003                    手续费率（默认 0.001）
    --method {sigma,atr,quantile}   上下限算法（默认 sigma）
    --safety 1.2                    上下限安全垫（默认 1.0，越大越宽）
    --max-grids 30                  自动格数上限（默认 60）
    --window 260                    分析多少根日线（默认 120 ≈ 6 个月）

  ${paint(C.bold, '示例:')}
    npx grid-trading-skill ask
    npx grid-trading-skill auto 600519 50000
    npx grid-trading-skill auto 00700 20000 --backtest
    npx grid-trading-skill auto BTC/USDT 10000 --method atr --safety 1.2
    npx grid-trading-skill auto AAPL 5000 --window 260
    npx grid-trading-skill run "BTC/USDT 40000~60000 20格 本金10000 手续费0.1%"
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
      case 'auto':               runAuto(args); break;
      case 'ask':                ask().catch((e) => { err(e.message || String(e)); process.exit(1); }); break;
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
