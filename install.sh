#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Grid Trading Skill — One-click installer for macOS / Linux
#
# Installs:
#   1. The Python package `grid_trading` (via pip)
#   2. Claude Code skill at ~/.claude/skills/grid-trading/
#   3. OpenAI Codex agent at ~/.codex/agents/grid-trading/ (if Codex installed)
#
# Usage:
#   bash install.sh                # install everything
#   bash install.sh --claude-only  # install only Claude Code skill
#   bash install.sh --codex-only   # install only Codex agent
#   bash install.sh --uninstall    # remove previously installed skill/agent
# -----------------------------------------------------------------------------

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_SKILL_DIR="${HOME}/.claude/skills/grid-trading"
CODEX_AGENT_DIR="${HOME}/.codex/agents/grid-trading"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[ OK ]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()   { echo -e "${RED}[ERR ]${NC} $*" >&2; }

# -----------------------------------------------------------------------------
# Parse args
# -----------------------------------------------------------------------------
MODE="all"
case "${1:-}" in
    --claude-only) MODE="claude" ;;
    --codex-only)  MODE="codex" ;;
    --uninstall)   MODE="uninstall" ;;
    "")            MODE="all" ;;
    -h|--help)
        head -n 14 "$0" | tail -n 13
        exit 0
        ;;
    *)
        err "Unknown flag: $1"
        exit 1
        ;;
esac

# -----------------------------------------------------------------------------
# Uninstall flow
# -----------------------------------------------------------------------------
if [[ "$MODE" == "uninstall" ]]; then
    info "Removing Claude Code skill..."
    rm -rf "$CLAUDE_SKILL_DIR" && ok "Removed $CLAUDE_SKILL_DIR" || true
    info "Removing Codex agent..."
    rm -rf "$CODEX_AGENT_DIR" && ok "Removed $CODEX_AGENT_DIR" || true
    info "Uninstalling Python package..."
    pip3 uninstall -y grid-trading-skill 2>/dev/null || true
    ok "Uninstall complete."
    exit 0
fi

# -----------------------------------------------------------------------------
# Detect Python
# -----------------------------------------------------------------------------
PY=""
for candidate in python3.13 python3.12 python3.11 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        VERSION=$("$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "0.0")
        MAJOR=$(echo "$VERSION" | cut -d. -f1)
        MINOR=$(echo "$VERSION" | cut -d. -f2)
        if [[ "$MAJOR" -ge 3 && "$MINOR" -ge 11 ]]; then
            PY="$candidate"
            break
        fi
    fi
done

if [[ -z "$PY" ]]; then
    err "Python 3.11+ not found."
    err "Install from https://www.python.org/downloads/ then re-run this script."
    exit 1
fi
ok "Using $PY ($("$PY" --version))"

# -----------------------------------------------------------------------------
# Install Python package
# -----------------------------------------------------------------------------
if [[ "$MODE" == "all" ]]; then
    info "Installing Python package (pip install .)..."
    "$PY" -m pip install --user --upgrade "$SCRIPT_DIR" >/dev/null 2>&1 || {
        warn "User install failed, retrying with --break-system-packages..."
        "$PY" -m pip install --user --break-system-packages --upgrade "$SCRIPT_DIR"
    }
    ok "Python package installed."
fi

# -----------------------------------------------------------------------------
# Install Claude Code skill
# -----------------------------------------------------------------------------
install_claude_skill() {
    info "Installing Claude Code skill → $CLAUDE_SKILL_DIR"
    mkdir -p "$CLAUDE_SKILL_DIR"
    # Copy SKILL.md and full source (so import works even without pip install)
    cp -R "$SCRIPT_DIR/grid_trading/." "$CLAUDE_SKILL_DIR/"
    ok "Claude Code skill installed."
    echo "     → Open Claude Code and type: /grid-trading"
}

# -----------------------------------------------------------------------------
# Install Codex agent
# -----------------------------------------------------------------------------
install_codex_agent() {
    info "Installing OpenAI Codex agent → $CODEX_AGENT_DIR"
    mkdir -p "$CODEX_AGENT_DIR"
    cp -R "$SCRIPT_DIR/grid_trading/." "$CODEX_AGENT_DIR/"
    # Codex CLI expects AGENTS.md — install one alongside SKILL.md
    if [[ -f "$SCRIPT_DIR/AGENTS.md" ]]; then
        cp "$SCRIPT_DIR/AGENTS.md" "$CODEX_AGENT_DIR/AGENTS.md"
    fi
    ok "Codex agent installed."
    echo "     → In Codex CLI, reference: grid-trading"
}

case "$MODE" in
    all)
        install_claude_skill
        install_codex_agent
        ;;
    claude) install_claude_skill ;;
    codex)  install_codex_agent ;;
esac

echo ""
ok "Installation complete!"
echo ""
echo "Quick start (Python):"
echo "  from grid_trading.strategy.grid_strategy import GridConfig, GridStrategy"
echo "  from grid_trading.backtest.simulator import BacktestSimulator"
echo ""
echo "Docs: $SCRIPT_DIR/README.md"
