# 🚀 v1.1.0 — One-Line npx Install

**亮点：新增跨平台 `npx` 一键安装，Mac / Linux / Windows 统一一条命令。**

## ✨ 新增

- 🌟 **Node CLI 安装器** — `npx github:JetQiao/grid-trading-skill` 立即可用
- 📦 发布为 npm 包 `grid-trading-skill`（可选 `npm install -g`）
- 🛠  CLI 子命令：`install`、`uninstall`、`status`、`help`
- 🎛  分端安装：`--claude-only` / `--codex-only`
- 🧹 无外部 npm 依赖，零安装体积（~40KB）
- ✅ Node 16+ 即可，不需要 Python 也能部署 skill 文件

## 📦 安装

```bash
# 推荐（无需发布 npm，直接从 GitHub）
npx github:JetQiao/grid-trading-skill

# 发布到 npm 之后
npx grid-trading-skill
# 或全局安装
npm install -g grid-trading-skill
```

其它原有方式仍支持：

```bash
bash install.sh                                     # macOS/Linux
powershell -ExecutionPolicy Bypass -File install.ps1  # Windows
pip install git+https://github.com/JetQiao/grid-trading-skill.git@v1.1.0
```

## 🔄 从 v1.0.0 升级

```bash
npx github:JetQiao/grid-trading-skill uninstall
npx github:JetQiao/grid-trading-skill
```

## 📥 Assets

- `grid-trading-skill-1.1.0.zip` — 完整源码
- `grid_trading_skill-1.1.0-py3-none-any.whl` — pip wheel
- `grid_trading_skill-1.1.0.tar.gz` — pip sdist

## 🔗 完整变更

<https://github.com/JetQiao/grid-trading-skill/compare/v1.0.0...v1.1.0>
