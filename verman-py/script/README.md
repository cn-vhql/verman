# VerMan 打包与右键菜单

`script/` 目录只保留当前还在使用的 Windows 打包和右键菜单脚本。

## 目录内容

- `build_exe_simple.py`：用 PyInstaller 打包单文件 GUI 程序
- `install_exe_menu.bat`：安装右键菜单入口
- `install_exe_context_menu.py`：写入 Windows 右键菜单注册表
- `uninstall_exe_menu.bat`：卸载右键菜单入口
- `uninstall_exe_context_menu.py`：删除 Windows 右键菜单注册表项

## 打包

在项目根目录执行：

```bash
python script/build_exe_simple.py
```

输出：

- `dist/VersionManager.exe`
- `build/`

当前脚本会生成单文件、无控制台窗口的 EXE，版本信息来自 `app_info.py`。

## 安装右键菜单

打包完成后执行：

```bash
script/install_exe_menu.bat
```

卸载：

```bash
script/uninstall_exe_menu.bat
```

右键菜单会把目录路径或文件路径传给 `VersionManager.exe`，程序会按以下规则处理：

- 目录路径：如果已是 VerMan 项目则直接打开，否则询问是否创建项目
- 文件路径：先取父目录，再按目录规则处理

## 环境要求

- Windows 10/11
- Python 3.8+
- 安装右键菜单时需要管理员权限
