#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VerMan EXE版本右键菜单卸载脚本
"""

import os
import sys
import winreg


def uninstall_context_menu():
    """卸载右键菜单"""
    try:
        # 删除的注册表项
        registry_keys = [
            r"Directory\Background\shell\VerMan",
            r"Directory\shell\VerMan",
            r"*\shell\VerMan"
        ]

        success_count = 0
        for key_path in registry_keys:
            try:
                winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, key_path + r"\command")
                winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, key_path)
                print(f"✓ 已删除: {key_path}")
                success_count += 1
            except FileNotFoundError:
                print(f"- 跳过: {key_path} (不存在)")
            except Exception as e:
                print(f"✗ 删除失败: {key_path} - {e}")

        if success_count > 0:
            print("✓ 右键菜单卸载成功")
            return True
        else:
            print("! 没有找到已安装的右键菜单项")
            return True

    except Exception as e:
        print(f"✗ 卸载失败: {e}")
        return False


def main():
    """主函数"""
    print("=" * 50)
    print("   VerMan EXE版本右键菜单卸载工具")
    print("=" * 50)
    print()

    # 检查是否在Windows系统
    if sys.platform != "win32":
        print("错误: 此脚本仅支持Windows系统")
        input("按回车键退出...")
        return False

    # 卸载右键菜单
    success = uninstall_context_menu()

    print()
    if success:
        print("卸载完成！")
        print("如需重新安装，请运行 script/install_exe_menu.bat")
    else:
        print("卸载失败，请检查权限设置")

    print()
    input("按回车键退出...")
    return success


if __name__ == "__main__":
    main()