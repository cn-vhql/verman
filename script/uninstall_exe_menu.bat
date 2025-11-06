@echo off
chcp 65001
title VerMan EXE版本右键菜单卸载工具

echo ========================================
echo    VerMan EXE版本右键菜单卸载工具
echo ========================================
echo.

cd /d "%~dp0\.."

echo 开始卸载EXE版本右键菜单...
python script\uninstall_exe_context_menu.py

echo.
echo 卸载完成！
echo.
pause