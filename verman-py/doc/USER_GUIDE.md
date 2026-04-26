# VerMan 用户指南

VerMan 是一个 Windows 优先的本地版本管理工具，用来给普通工作目录做轻量版本快照、查看差异、导出历史和安全回滚。

## 当前版本行为

- 所有项目元数据统一放在工作区根目录下的 `.verman/`
- 根目录只保留 `.vermanignore` 作为用户可编辑的忽略规则文件
- 回滚会按目标版本严格恢复工作区，并删除目标版本中不存在的当前文件
- 长操作在后台串行执行，界面只负责状态显示和结果回调

## 快速开始

1. 启动程序
   - 直接运行 `python main.py`
   - 或运行 `python main.py <path>`
2. 创建项目
   - 在菜单里选择“项目 -> 新建项目”
   - 选择一个本地目录
   - VerMan 会在该目录创建 `.verman/` 和 `.vermanignore`
3. 提交版本
   - 先点击“刷新”
   - 确认变更列表
   - 点击“提交版本”并填写说明
4. 回滚版本
   - 在右侧版本列表选择目标版本
   - 点击“回滚选中版本”
   - 如启用了自动备份，会先备份当前工作区到 `.verman/backup/`

## 项目目录结构

```text
workspace/
  .verman/
    project.db
    project.db-wal
    project.db-shm
    backup/
  .vermanignore
```

说明：

- `project.db` 是版本数据库
- `project.db-wal` 和 `project.db-shm` 是 SQLite 在 WAL 模式下的工作文件
- `backup/` 用于保存回滚前的工作区备份
- `.vermanignore` 保持在根目录，方便直接编辑

## 启动参数和右键入口

- `verman`
  - 正常启动，手动选择项目
- `verman <目录路径>`
  - 如果目录里已有 VerMan 项目，直接打开
  - 如果目录还不是 VerMan 项目，程序会询问是否立即创建
- `verman <文件路径>`
  - 自动取该文件的父目录，再按目录规则处理

Windows 右键菜单安装后，目录、目录空白处和文件都可以把路径传给 VerMan。

## 变更扫描规则

- 刷新时先读取文件大小和 `mtime_ns`
- 未变化文件直接复用索引中的旧 hash
- 只有新增或疑似变化文件才重新读取并计算 hash
- 刚刷新后的扫描结果会缓存，提交版本时直接复用，不再额外全量重扫
- `.verman/` 元数据目录会被自动忽略，不会进入版本历史

## 历史版本行为

- 版本详情、导出、版本比较都基于同一套“有效版本文件”重建逻辑
- 在版本详情中双击文件：
  - `add` / `modify` 打开该版本存储的内容
  - `unmodified` 从当前项目根目录读取对应文件
  - `delete` 不会尝试打开不存在的文件

## 设置项

当前保留的设置只有：

- 最近项目列表
- 窗口大小与位置 `window_geometry`
- 忽略规则 `ignore_patterns`
- 回滚前自动备份 `auto_backup`

## 忽略规则

项目根目录的 `.vermanignore` 使用逐行匹配规则，支持常见通配符。

示例：

```text
build/
dist/
.venv/
__pycache__/
*.log
*.tmp
```

默认还会忽略 VerMan 自身元数据目录、常见缓存目录和系统临时文件。

## 旧项目迁移

旧版项目如果还在根目录使用这些文件：

```text
.verman.db
.verman.db-wal
.verman.db-shm
.verman_backup/
```

打开时会自动迁移到新的 `.verman/` 结构。

如果旧数据库还需要 schema 升级，程序会先生成数据库备份：

```text
.verman/project.db.bak.YYYYMMDD_HHMMSS
```

随后只做增量 schema 升级：

- 新增 `workspace_index`
- 新增 `config['schema_version']`
- 补齐索引

历史 `versions/files` 数据会保留，不会重写成新的存储模型。

## 常见问题

### 为什么第二次刷新明显更快？

因为 VerMan 会复用 `workspace_index` 中未变化文件的 hash，不会重复读取全部文件内容。

### 回滚后为什么有些新文件被删了？

这是当前版本的设计。回滚会让工作区严格回到目标版本状态，不保留目标版本中不存在的当前文件。

### 数据是否会上传？

不会。当前版本没有在线同步或商业化能力，所有版本数据只保存在本地项目目录。
