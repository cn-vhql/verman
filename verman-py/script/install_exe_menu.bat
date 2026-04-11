@echo off
chcp 65001
title VerMan EXE版本右键菜单安装工具

echo ========================================
echo    VerMan EXE版本右键菜单安装工具
echo ========================================
echo.

cd /d "%~dp0\.."

echo 检查Python环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python，请先安装Python
    pause
    exit /b 1
)
echo [成功] Python环境检查通过
echo.

echo 检查exe文件...
if not exist "VersionManager.exe" (
    if not exist "dist\VersionManager.exe" (
        echo [警告] 未找到VersionManager.exe文件
        echo 将检查dist目录...
        if not exist "dist" (
            echo [错误] 请先运行 script\build_exe_simple.py 打包程序
            pause
            exit /b 1
        )
    )
)
echo [成功] EXE文件检查通过
echo.

echo 开始安装EXE版本右键菜单...
python script\install_exe_context_menu.py

echo.
echo 安装完成！
echo.
echo 使用说明：
echo • 在任意文件夹上右键 -^> 选择"使用VerMan版本管理"
echo • 在文件夹空白处右键 -^> 选择"使用VerMan版本管理"
echo • 在文件上右键 -^> 选择"使用VerMan版本管理"
echo.
echo 卸载方法：运行 script\uninstall_exe_menu.bat
echo.
pause