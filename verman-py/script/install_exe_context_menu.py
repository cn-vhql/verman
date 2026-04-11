#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VerMan EXE版本右键菜单安装脚本
自动检测exe文件位置并安装到Windows右键菜单
"""

import os
import sys
import winreg
from pathlib import Path


def find_exe_path():
    """查找exe文件位置"""
    # 获取项目根目录
    project_root = Path(__file__).parent.parent
    current_dir = project_root

    # 可能的exe文件位置
    possible_paths = [
        current_dir / "dist" / "VersionManager.exe",
        current_dir / "VersionManager.exe",
        current_dir / "build" / "exe.win-amd64-3.11" / "VersionManager.exe",
        current_dir / "build" / "exe.win32-3.11" / "VersionManager.exe",
    ]

    print("正在查找VersionManager.exe...")
    for path in possible_paths:
        if path.exists():
            print(f"找到exe文件: {path}")
            return str(path)
        else:
            print(f"检查位置: {path} - 未找到")

    return None


def install_context_menu(exe_path):
    """安装右键菜单"""
    try:
        # 创建目录背景右键菜单
        with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, r"Directory\\Background\\shell\\VerMan") as key:
            winreg.SetValueEx(key, None, 0, winreg.REG_SZ, "使用VerMan版本管理")
            with winreg.CreateKey(key, "command") as cmd_key:
                winreg.SetValueEx(cmd_key, None, 0, winreg.REG_SZ, f'"{exe_path}" "%V"')

        # 创建文件夹右键菜单
        with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, r"Directory\\shell\\VerMan") as key:
            winreg.SetValueEx(key, None, 0, winreg.REG_SZ, "使用VerMan版本管理")
            with winreg.CreateKey(key, "command") as cmd_key:
                winreg.SetValueEx(cmd_key, None, 0, winreg.REG_SZ, f'"{exe_path}" "%1"')

        # 创建文件右键菜单
        with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, r"*\\shell\\VerMan") as key:
            winreg.SetValueEx(key, None, 0, winreg.REG_SZ, "使用VerMan版本管理")
            with winreg.CreateKey(key, "command") as cmd_key:
                winreg.SetValueEx(cmd_key, None, 0, winreg.REG_SZ, f'"{exe_path}" "%1"')

        print("✓ 右键菜单安装成功")
        return True

    except Exception as e:
        print(f"✗ 安装失败: {e}")
        return False


def main():
    """主函数"""
    print("=" * 50)
    print("   VerMan EXE版本右键菜单安装工具")
    print("=" * 50)
    print()

    # 检查是否在Windows系统
    if sys.platform != "win32":
        print("错误: 此脚本仅支持Windows系统")
        input("按回车键退出...")
        return False

    # 查找exe文件
    exe_path = find_exe_path()
    if not exe_path:
        print("错误: 未找到VersionManager.exe文件")
        print("请先运行 script/build_exe_simple.py 打包程序")
        input("按回车键退出...")
        return False

    # 验证exe文件
    if not os.path.exists(exe_path):
        print(f"错误: exe文件不存在: {exe_path}")
        input("按回车键退出...")
        return False

    print(f"使用exe文件: {exe_path}")
    print()

    # 安装右键菜单
    success = install_context_menu(exe_path)

    print()
    if success:
        print("安装完成！")
        print()
        print("使用说明：")
        print("• 在任意文件夹上右键 → 选择'使用VerMan版本管理'")
        print("• 在文件夹空白处右键 → 选择'使用VerMan版本管理'")
        print("• 在文件上右键 → 选择'使用VerMan版本管理'")
        print()
        print("卸载方法：运行 script/uninstall_exe_menu.bat")
    else:
        print("安装失败，请检查权限设置")

    print()
    input("按回车键退出...")
    return success


if __name__ == "__main__":
    main()