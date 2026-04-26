#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VerMan EXE context menu installer.
"""

import os
import sys
import winreg
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app_info import APP_EXECUTABLE_NAME
from runtime_paths import find_packaged_executable


def find_exe_path():
    """Locate the packaged executable for registry registration."""
    print(f"正在查找 {APP_EXECUTABLE_NAME} ...")
    exe_path = find_packaged_executable(search_roots=[PROJECT_ROOT])
    if exe_path:
        print(f"找到 exe 文件: {exe_path}")
    else:
        print(f"未找到 {APP_EXECUTABLE_NAME}")
    return exe_path


def install_context_menu(exe_path):
    """Install Windows Explorer context menu entries."""
    try:
        with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, r"Directory\Background\shell\VerMan") as key:
            winreg.SetValueEx(key, None, 0, winreg.REG_SZ, "使用VerMan版本管理")
            with winreg.CreateKey(key, "command") as cmd_key:
                winreg.SetValueEx(cmd_key, None, 0, winreg.REG_SZ, f'"{exe_path}" "%V"')

        with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, r"Directory\shell\VerMan") as key:
            winreg.SetValueEx(key, None, 0, winreg.REG_SZ, "使用VerMan版本管理")
            with winreg.CreateKey(key, "command") as cmd_key:
                winreg.SetValueEx(cmd_key, None, 0, winreg.REG_SZ, f'"{exe_path}" "%1"')

        with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, r"*\shell\VerMan") as key:
            winreg.SetValueEx(key, None, 0, winreg.REG_SZ, "使用VerMan版本管理")
            with winreg.CreateKey(key, "command") as cmd_key:
                winreg.SetValueEx(cmd_key, None, 0, winreg.REG_SZ, f'"{exe_path}" "%1"')

        print("✓ 右键菜单安装成功")
        return True
    except Exception as exc:
        print(f"✗ 安装失败: {exc}")
        return False


def main():
    """CLI entrypoint."""
    print("=" * 50)
    print("   VerMan EXE版本右键菜单安装工具")
    print("=" * 50)
    print()

    if sys.platform != "win32":
        print("错误: 此脚本仅支持 Windows 系统")
        input("按回车键退出...")
        return False

    exe_path = find_exe_path()
    if not exe_path:
        print(f"错误: 未找到 {APP_EXECUTABLE_NAME}")
        print("请先运行 script/build_exe_simple.py 打包程序")
        input("按回车键退出...")
        return False

    if not os.path.exists(exe_path):
        print(f"错误: exe 文件不存在: {exe_path}")
        input("按回车键退出...")
        return False

    print(f"使用 exe 文件: {exe_path}")
    print()

    success = install_context_menu(exe_path)

    print()
    if success:
        print("安装完成！")
        print("卸载方法：运行 script/uninstall_exe_menu.bat")
    else:
        print("安装失败，请检查权限设置")

    print()
    input("按回车键退出...")
    return success


if __name__ == "__main__":
    main()
