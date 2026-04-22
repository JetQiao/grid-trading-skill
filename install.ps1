# -----------------------------------------------------------------------------
# Grid Trading Skill — One-click installer for Windows (PowerShell)
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File install.ps1
#   powershell -ExecutionPolicy Bypass -File install.ps1 -Mode claude
#   powershell -ExecutionPolicy Bypass -File install.ps1 -Mode codex
#   powershell -ExecutionPolicy Bypass -File install.ps1 -Uninstall
# -----------------------------------------------------------------------------

param(
    [ValidateSet("all", "claude", "codex")]
    [string]$Mode = "all",
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$ScriptDir       = Split-Path -Parent $MyInvocation.MyCommand.Path
$ClaudeSkillDir  = Join-Path $HOME ".claude\skills\grid-trading"
$CodexAgentDir   = Join-Path $HOME ".codex\agents\grid-trading"

function Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Blue }
function Ok($msg)   { Write-Host "[ OK ] $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Err($msg)  { Write-Host "[ERR ] $msg" -ForegroundColor Red }

# Uninstall flow
if ($Uninstall) {
    Info "Removing Claude Code skill..."
    if (Test-Path $ClaudeSkillDir) { Remove-Item -Recurse -Force $ClaudeSkillDir; Ok "Removed $ClaudeSkillDir" }
    Info "Removing Codex agent..."
    if (Test-Path $CodexAgentDir) { Remove-Item -Recurse -Force $CodexAgentDir; Ok "Removed $CodexAgentDir" }
    Info "Uninstalling Python package..."
    pip uninstall -y grid-trading-skill 2>$null
    Ok "Uninstall complete."
    exit 0
}

# Detect Python 3.11+
$py = $null
foreach ($c in @("python", "python3", "py")) {
    try {
        $v = & $c -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($v -match "^3\.(1[1-9]|[2-9]\d)") { $py = $c; break }
    } catch {}
}
if (-not $py) {
    Err "Python 3.11+ not found. Install from https://www.python.org/downloads/"
    exit 1
}
Ok "Using $py ($(& $py --version))"

if ($Mode -eq "all") {
    Info "Installing Python package..."
    & $py -m pip install --user --upgrade $ScriptDir | Out-Null
    Ok "Python package installed."
}

function Install-ClaudeSkill {
    Info "Installing Claude Code skill -> $ClaudeSkillDir"
    New-Item -ItemType Directory -Force -Path $ClaudeSkillDir | Out-Null
    Copy-Item -Recurse -Force "$ScriptDir\grid_trading\*" $ClaudeSkillDir
    Ok "Claude Code skill installed."
    Write-Host "     -> Open Claude Code and type: /grid-trading"
}

function Install-CodexAgent {
    Info "Installing OpenAI Codex agent -> $CodexAgentDir"
    New-Item -ItemType Directory -Force -Path $CodexAgentDir | Out-Null
    Copy-Item -Recurse -Force "$ScriptDir\grid_trading\*" $CodexAgentDir
    $agentsPath = Join-Path $ScriptDir "AGENTS.md"
    if (Test-Path $agentsPath) {
        Copy-Item -Force $agentsPath (Join-Path $CodexAgentDir "AGENTS.md")
    }
    Ok "Codex agent installed."
    Write-Host "     -> In Codex CLI, reference: grid-trading"
}

switch ($Mode) {
    "all"    { Install-ClaudeSkill; Install-CodexAgent }
    "claude" { Install-ClaudeSkill }
    "codex"  { Install-CodexAgent }
}

Write-Host ""
Ok "Installation complete!"
Write-Host "Docs: $ScriptDir\README.md"
