# VerMan

VerMan 是一个 Windows 优先的本地版本管理工具，用来给普通工作目录做轻量快照、查看历史差异、导出版本内容和安全回滚。

## 当前定位

- 本地优先，所有数据都保存在项目目录下的 `.verman.db`
- 不做云同步，不包含 VIP、激活或商业化模块
- 旧项目打开时会先自动备份数据库，再执行 schema 升级
- 当前不再对单个文件大小设置硬性上限

## 主要能力

- 创建并打开 VerMan 项目
- 刷新工作区，识别新增、修改、删除
- 提交版本快照并记录说明
- 查看版本详情和两个版本之间的差异
- 导出历史版本内容
- 将工作区严格回滚到指定版本
- 支持通过 Windows 右键菜单传入目录或文件路径启动

## 性能和稳定性行为

- 刷新时优先复用 `workspace_index` 中未变化文件的 hash，只对新增或疑似变化文件重新读取内容
- 提交版本会直接复用最近一次刷新得到的 `ScanSnapshot`，避免“刷新后再全量重扫一次”
- 刷新、提交、回滚、导出、比较等长操作都走后台串行 worker，GUI 主线程只负责状态更新和回调
- 回滚按目标版本清单恢复工作区，并删除目标版本中不存在的当前文件

## 启动方式

```bash
python main.py
python main.py path\to\workspace
```

安装为命令行入口后也支持：

```bash
verman
verman path\to\workspace
```

启动参数行为：

- 传入目录且目录已经是 VerMan 项目时，直接打开
- 传入目录但目录还不是 VerMan 项目时，弹窗询问是否立即创建
- 传入文件路径时，自动取父目录后按目录规则处理

## 开发与测试

```bash
python -m unittest discover -s tests -v
```

打包单文件 EXE：

```bash
python script/build_exe_simple.py
```

产物默认输出到 `dist/VersionManager.exe`，当前版本号为 `V1.0.1`。

## 主要模块

- `main.py`：程序入口，支持可选启动路径
- `gui.py`：Tkinter 主界面和后台任务调度
- `version_manager.py`：版本管理核心逻辑
- `file_manager.py`：扫描、恢复、导出、备份
- `database.py`：SQLite 存储和迁移
- `project_manager.py`：项目创建、打开、关闭
- `dialogs.py`：版本详情和版本比较对话框
- `models.py`：共享模型和数据结构
