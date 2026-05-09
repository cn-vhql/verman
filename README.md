# VerMan — 轻量级本地文件版本管理

VerMan 是一个轻量级的本地文件版本管理工具，类似 SVN 但无需服务器，直接对工作区文件进行版本快照、回滚和比较。

## 主要功能

- **文件变更检测** — 扫描工作区，自动识别新增、修改、删除的文件
- **版本快照** — 将当前文件状态保存为版本，支持描述信息
- **版本回滚** — 恢复到任意历史版本，支持备份当前状态
- **版本导出** — 将某个版本的文件导出到指定目录
- **版本比较** — 对比两个版本之间的文件差异
- **操作日志** — 记录所有版本操作历史
- **Windows 右键菜单** — 在资源管理器中直接打开 VerMan

## 技术栈

- **前端**: Svelte 5 + TypeScript + Vite
- **后端**: Rust + Tauri 2
- **数据库**: SQLite (rusqlite)
- **哈希**: MD5
- **并行计算**: Rayon
- **文件监控**: notify

## 构建要求

- Rust 1.75+
- Node.js 18+
- pnpm 9+

## 开发

```bash
# 安装依赖
pnpm install

# 启动开发模式
pnpm tauri dev

# 构建安装包
pnpm tauri build
```

## 项目结构

```
verman-rust/
├── src/                    # Svelte 前端
│   ├── App.svelte          # 主界面
│   ├── lib/
│   │   ├── commands.ts     # Tauri 命令绑定
│   │   ├── types.ts        # TypeScript 类型
│   │   └── components/     # UI 组件
│   └── main.ts
├── src-tauri/              # Rust 后端
│   └── src/
│       ├── commands.rs     # Tauri 命令处理
│       ├── database.rs     # SQLite 数据库操作
│       ├── file_manager.rs # 文件扫描与哈希
│       ├── version_manager.rs # 版本管理核心逻辑
│       ├── project_manager.rs # 项目管理
│       ├── file_watcher.rs # 文件系统监听
│       └── models.rs       # 数据模型
└── package.json
```

## 许可

MIT
