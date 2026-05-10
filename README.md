# VerMan — 轻量级本地文件版本管理

[English Version](README_EN.md)

---

## 📖 这是一款怎样的产品？

你是否曾经在修改文件前，犹豫着复制一份「备份」？是否在项目目录里见过一堆 `xxx_最终版.txt`、`xxx_最终版2.txt`？是否在改完代码后发现改错了，却找不到原来的版本？

**VerMan 就是为解决这些问题而生。**

它是一款**本地文件版本管理工具**，灵感来自 SVN 的版本概念，但去掉了服务器的复杂度。你不需要搭建服务、不需要联网、不需要学习复杂的命令。右键点击目录，打开 VerMan，就能对当前文件状态打一个「快照」。任何时候都能一键回滚到任意历史版本，或者导出某个版本的文件。

VerMan 的核心哲学是：**版本管理应该像喝水一样简单**。它不替代 Git/SVN，而是填补那个「我只是想保留一下当前状态，不想折腾仓库」的场景。

## 🚀 核心能力

| 功能 | 说明 |
|------|------|
| **文件变更检测** | 扫描工作区，自动识别新增、修改、删除的文件，变更状态一目了然 |
| **版本快照** | 将当前文件状态保存为一个版本，支持添加描述说明 |
| **版本回滚** | 一键恢复到任意历史版本，支持回滚前自动备份当前状态 |
| **版本导出** | 将某个历史版本的文件导出到任意目录 |
| **版本比较** | 对比两个版本之间的文件差异，快速定位变更内容 |
| **操作日志** | 记录所有版本操作历史，可追溯每一次变更 |
| **Windows 右键菜单** | 在资源管理器中右键目录或文件，一键打开 VerMan |
| **自动文件监听** | 文件变更后自动刷新状态，无需手动操作 |
| **大文件支持** | 自动将大文件内容外置存储，数据库轻量化，性能不受影响 |
| **忽略规则** | 支持 `.vermanignore` 忽略模式，灵活控制哪些文件纳入版本管理 |

## 🎯 适用场景

- **设计师/文案工作者** — 保存设计稿或文档的不同版本，随时回溯
- **开发者** — 在实验性修改前打快照，快速回滚试错
- **运维人员** — 对配置文件做版本管理，变更可追溯
- **普通用户** — 任何需要「保留文件历史」的场景

## ✨ 易用性设计

- **零配置启动**：下载安装后，右键目录 → 打开 VerMan → 一键创建项目
- **图形化界面**：所有操作皆通过直观的 UI 完成，无需记忆命令
- **智能默认值**：自动忽略 `.verman/` 元数据目录，开箱即用
- **实时反馈**：进度条实时显示长操作进度，操作日志追踪每一步
- **安全回滚**：回滚前可选自动备份当前状态，防止误操作

---

## 你不需要另一个 Git

Git 很好，但有些场景它太重了。你只是想在修改一批文档之前留个底，或者想看看上周的配置文件和现在有什么不同，又或者想回溯一下项目某个历史状态——这些事用 Git 需要初始化仓库、写提交信息、推送远程……而用 VerMan，只需要**右键 → 创建版本**。

**你的文件，永远在你手里。**

VerMan 没有云同步，没有订阅制，没有数据泄露风险。所有数据都保存在你的工作目录下的 `.verman/` 文件夹里。不依赖网络，不依赖第三方服务。你随时可以复制、迁移、删除——你的数据你做主。

**从 Python 到 Rust，我们认真打磨。**

VerMan 最初用 Python 构建，快速验证了产品理念。随后用 Rust/Tauri 完全重写，带来了真正的性能飞跃：毫秒级的文件扫描、极低的内存占用、原生级别的启动速度和安装体验。这不是一个「写着玩玩」的工具，而是一个认真对待每一个文件版本的产品。

如果你还在用「复制→粘贴→重命名」的方式管理文件版本，是时候试试 VerMan 了。

---

## 技术栈

### Rust 版本 (主推)

| 层级 | 技术 |
|------|------|
| 前端 | Svelte 5 + TypeScript + Vite |
| 后端 | Rust + Tauri 2 |
| 数据库 | SQLite (rusqlite, WAL 模式) |
| 文件哈希 | MD5 (md-5 crate) |
| 并行计算 | Rayon |
| 文件监控 | notify (300ms 去抖) |
| 缓存 | LRU 哈希缓存 + 磁盘持久化 |

### Python 版本 (试用)

- Python 3.8+ / Tkinter GUI
- 功能完整，适合快速试用或二次开发

## 安装

### Rust 版本 (推荐)

从 [GitHub Releases](https://github.com/cn-vhql/verman/releases) 下载最新 MSI 或 NSIS 安装包运行即可。

### Python 版本

```bash
git clone https://github.com/cn-vhql/verman.git
cd verman/verman-py
uv sync
uv run python main.py
```

## 使用入门

### Rust 版本

```bash
cd verman-rust
pnpm install
pnpm tauri dev    # 开发模式
pnpm tauri build  # 构建安装包
```

### Python 版本

```bash
cd verman-py
uv run python main.py                    # 运行
uv run python main.py path/to/workspace  # 指定目录
uv run python -m unittest discover -s tests -v  # 运行测试
```

## 项目结构

```
verman/
├── verman-rust/              # Rust/Tauri 版本 (主推)
│   ├── src/                  # Svelte 前端
│   │   ├── App.svelte        # 主界面
│   │   ├── lib/
│   │   │   ├── commands.ts   # Tauri 命令绑定
│   │   │   ├── types.ts      # TypeScript 类型定义
│   │   │   └── components/   # UI 组件
│   │   └── main.ts
│   ├── src-tauri/            # Rust 后端
│   │   └── src/
│   │       ├── commands.rs       # Tauri 命令处理层
│   │       ├── database.rs       # SQLite 数据库 (WAL 模式)
│   │       ├── file_manager.rs   # 文件扫描、哈希、缓存
│   │       ├── version_manager.rs # 版本管理核心逻辑
│   │       ├── project_manager.rs # 项目管理
│   │       ├── file_watcher.rs   # 文件系统监听
│   │       ├── config.rs         # 用户配置管理
│   │       ├── project_paths.rs  # 项目路径工具
│   │       ├── logger.rs         # 操作日志
│   │       ├── models.rs         # 数据模型
│   │       └── lib.rs            # 库入口
│   └── package.json
├── verman-py/                # Python 版本 (试用)
│   ├── main.py               # 入口
│   ├── gui.py                # Tkinter 界面
│   ├── version_manager.py    # 版本管理核心
│   ├── file_manager.py       # 文件管理
│   ├── database.py           # 数据库
│   ├── project_manager.py    # 项目管理
│   ├── tests/                # 测试
│   └── script/               # 构建脚本
├── .github/workflows/        # GitHub Actions CI
└── README.md                 # 本文档
```

## 许可

本项目仅供**个人使用**，未经授权不得用于商业用途。

欢迎大家 ⭐ **加星**、🍴 **Fork**，共同参与项目建设！

## 贡献

如果你有任何想法或建议，欢迎提交 Issue 或 Pull Request，一起让 VerMan 变得更好。
