# VerMan — Lightweight Local File Version Management

[中文版本](README.md)

---

## 📖 What is VerMan?

Have you ever hesitated before editing a file, thinking you should make a "backup copy" first? Ever found your project directory littered with `xxx_final.txt`, `xxx_final_2.txt`, `xxx_really_final.txt`? Ever made changes to code only to realize you can't get the original back?

**VerMan was built to solve exactly these problems.**

It's a **local file version management tool** inspired by SVN's versioning concept, but without the server complexity. No servers to set up, no internet required, no complex commands to learn. Right-click a directory, open VerMan, and take a snapshot of your current file state. Roll back to any historical version with one click, or export files from any version.

VerMan's core philosophy: **Version management should be as simple as drinking water.** It doesn't replace Git/SVN — it fills the gap for those "I just want to save the current state without setting up a whole repository" moments.

## 🚀 Core Features

| Feature | Description |
|---------|-------------|
| **Change Detection** | Scans workspace, auto-detects added, modified, and deleted files |
| **Version Snapshots** | Save current file state as a version with optional description |
| **Version Rollback** | One-click restore to any historical version with optional auto-backup |
| **Version Export** | Export files from any historical version to any directory |
| **Version Comparison** | Compare file differences between any two versions |
| **Operation Log** | Records all version operations for full traceability |
| **Windows Context Menu** | Right-click any directory or file to open VerMan instantly |
| **Auto File Watching** | Automatically refreshes on file changes — no manual refresh needed |
| **Large File Support** | Large file content stored externally, keeping the database lean |
| **Ignore Rules** | `.vermanignore` patterns for flexible exclusion control |

## 🎯 Use Cases

- **Designers & Writers** — Save iterations of design files or documents, revisit any version
- **Developers** — Take snapshots before experimental changes, rollback freely
- **DevOps Engineers** — Version control config files with full change history
- **Everyday Users** — Any scenario where "keeping file history" matters

## ✨ Ease of Use

- **Zero configuration**: Install → right-click → open VerMan → create project
- **Graphical interface**: All operations through intuitive UI, no commands to memorize
- **Smart defaults**: Auto-ignores `.verman/` metadata directory, works out of the box
- **Real-time feedback**: Progress bars for long operations, detailed operation logs
- **Safe rollback**: Optional auto-backup before rollback prevents data loss

---

## Why You'll Love VerMan

**You don't need another Git.**

Git is great, but in some scenarios it's overkill. You just want to save a snapshot before editing a batch of documents. You want to see what changed in a config file since last week. You want to go back to a known-good state. For Git, that means initializing a repo, writing commit messages, pushing to remote... With VerMan, it's just **right-click → create version**.

**Your files, always in your hands.**

VerMan has no cloud sync, no subscriptions, no data leak risks. All data lives in the `.verman/` folder inside your workspace. No network dependency, no third-party services. You can copy, migrate, or delete it anytime — your data, your rules.

**From Python to Rust, we've been serious about this.**

VerMan started as a Python prototype to validate the concept, then was fully rewritten in Rust/Tauri. The result: millisecond-level file scanning, minimal memory footprint, native startup speed, and a smooth installation experience. This isn't a toy project — it's a product that takes every file version seriously.

If you're still managing file versions by "copy → paste → rename", it's time to try VerMan.

---

## Tech Stack

### Rust Version (Recommended)

| Layer | Technology |
|-------|------------|
| Frontend | Svelte 5 + TypeScript + Vite |
| Backend | Rust + Tauri 2 |
| Database | SQLite (rusqlite, WAL mode) |
| Hashing | MD5 (md-5 crate) |
| Parallel | Rayon |
| File Watching | notify (300ms debounce) |
| Caching | LRU hash cache + disk persistence |

### Python Version (Legacy)

- Python 3.8+ / Tkinter GUI
- Feature-complete, suitable for quick trials or customization

## Installation

### Rust Version (Recommended)

Download the latest MSI or NSIS installer from [GitHub Releases](https://github.com/cn-vhql/verman/releases).

### Python Version

```bash
git clone https://github.com/cn-vhql/verman.git
cd verman/verman-py
uv sync
uv run python main.py
```

## Quick Start

### Rust Version

```bash
cd verman-rust
pnpm install
pnpm tauri dev    # Development mode
pnpm tauri build  # Build installer
```

### Python Version

```bash
cd verman-py
uv run python main.py                    # Run
uv run python main.py path/to/workspace  # Open specific directory
uv run python -m unittest discover -s tests -v  # Run tests
```

## Project Structure

```
verman/
├── verman-rust/              # Rust/Tauri version (recommended)
│   ├── src/                  # Svelte frontend
│   │   ├── App.svelte        # Main interface
│   │   ├── lib/
│   │   │   ├── commands.ts   # Tauri command bindings
│   │   │   ├── types.ts      # TypeScript type definitions
│   │   │   └── components/   # UI components
│   │   └── main.ts
│   ├── src-tauri/            # Rust backend
│   │   └── src/
│   │       ├── commands.rs       # Tauri command handlers
│   │       ├── database.rs       # SQLite database (WAL mode)
│   │       ├── file_manager.rs   # File scanning, hashing, caching
│   │       ├── version_manager.rs # Core version management logic
│   │       ├── project_manager.rs # Project management
│   │       ├── file_watcher.rs   # File system watcher (notify)
│   │       ├── config.rs         # User configuration
│   │       ├── project_paths.rs  # Path utilities
│   │       ├── logger.rs         # Operation logging
│   │       ├── models.rs         # Data models
│   │       └── lib.rs            # Library entry
│   └── package.json
├── verman-py/                # Python version (legacy)
│   ├── main.py               # Entry point
│   ├── gui.py                # Tkinter GUI
│   ├── version_manager.py    # Version management core
│   ├── file_manager.py       # File management
│   ├── database.py           # Database
│   ├── project_manager.py    # Project management
│   ├── tests/                # Tests
│   └── script/               # Build scripts
├── .github/workflows/        # GitHub Actions CI
└── README.md                 # Chinese documentation
```

## License

This project is licensed for **personal use only**. Commercial use is not permitted without authorization.

⭐ **Star** and 🍴 **Fork** the project on GitHub — contributions are welcome!

## Contributing

Feel free to open Issues or submit Pull Requests. Let's make VerMan better together.
