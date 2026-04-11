# VerMan 打包和部署说明

本目录包含 VerMan 版本管理系统的打包和部署脚本，用于将 Python 程序打包成独立的 Windows 可执行文件。

## 文件说明

### 打包脚本
- **`build_exe_simple.py`** - 主打包脚本，使用 PyInstaller 将程序打包成 exe
- **`install_exe_menu.bat`** - 安装右键菜单快捷方式（批处理）
- **`install_exe_context_menu.py`** - 安装右键菜单的核心 Python 脚本
- **`uninstall_exe_menu.bat`** - 卸载右键菜单快捷方式（批处理）
- **`uninstall_exe_context_menu.py`** - 卸载右键菜单的核心 Python 脚本

## 使用步骤

### 1. 打包程序

运行打包脚本：
```bash
python script/build_exe_simple.py
```

或者直接双击运行 `script/build_exe_simple.py`

打包完成后，会生成：
- `dist/VersionManager.exe` - 主程序可执行文件
- `build/` - 临时构建文件（可删除）

### 2. 安装右键菜单

打包成功后，运行右键菜单安装脚本：
```bash
script/install_exe_menu.bat
```

或者双击运行 `script/install_exe_menu.bat`

### 3. 使用程序

安装完成后，可以通过以下方式使用：

1. **直接运行**：双击 `dist/VersionManager.exe`
2. **右键菜单**：
   - 在任意文件夹上右键 → 选择"使用VerMan版本管理"
   - 在文件夹空白处右键 → 选择"使用VerMan版本管理"
   - 在文件上右键 → 选择"使用VerMan版本管理"

### 4. 卸载程序

如需卸载右键菜单：
```bash
script/uninstall_exe_menu.bat
```

## 系统要求

- Windows 10/11
- Python 3.8+ （仅打包时需要）
- 管理员权限 （安装右键菜单时需要）

## 打包特性

### 优化配置
- **无控制台窗口**：程序以 GUI 模式运行
- **UPX 压缩**：减小文件体积
- **自动依赖检测**：包含所有必要的库文件
- **单文件打包**：所有依赖打包在一个 exe 中

### 自动包含的依赖
- SQLite3 数据库支持
- Tkinter GUI 组件
- 所有必要的 Python 标准库

## 故障排除

### 常见问题

1. **打包失败**
   - 确保 Python 环境正常
   - 检查网络连接（需要下载 PyInstaller）
   - 关闭杀毒软件重试

2. **找不到 exe 文件**
   - 确认打包成功完成
   - 检查 `dist/` 目录是否存在 `VersionManager.exe`

3. **右键菜单安装失败**
   - 以管理员身份运行安装脚本
   - 确认 exe 文件存在
   - 检查 Windows 注册表权限

4. **程序启动失败**
   - 确认目标系统兼容性
   - 检查防病毒软件是否拦截
   - 尝试以管理员身份运行

### 重新打包

如需重新打包：
1. 删除 `build/`、`dist/` 目录和 `.spec` 文件
2. 重新运行 `build_exe_simple.py`

## 技术细节

### PyInstaller 配置
脚本会自动生成 `VersionManager.spec` 配置文件，包含：
- 主入口：`gui_main.py`
- 隐藏导入：tkinter 组件和 sqlite3
- 单文件输出：`VersionManager.exe`
- 无控制台窗口

### 右键菜单注册表项
程序会在 Windows 注册表中创建以下项：
- `HKEY_CLASSES_ROOT\Directory\Background\shell\VerMan` - 目录背景右键菜单
- `HKEY_CLASSES_ROOT\Directory\shell\VerMan` - 文件夹右键菜单
- `HKEY_CLASSES_ROOT\*\shell\VerMan` - 文件右键菜单

### 路径处理
- 所有脚本使用相对路径引用
- 自动检测 exe 文件位置
- 支持多种常见的构建输出路径

## 许可证

本打包脚本遵循与主项目相同的许可证。

## 支持

如遇问题，请检查：
1. Python 环境是否正常
2. 是否有足够的磁盘空间
3. 是否有管理员权限
4. 防病毒软件是否阻止操作