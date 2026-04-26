#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VerMan打包脚本 - 简单版本
将VerMan打包成独立的exe可执行文件
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app_info import APP_NAME, APP_DISPLAY_VERSION, APP_VERSION_NUMBER


def run_command(command, description=""):
    """运行命令并处理结果"""
    print(f"执行: {description or command}")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, encoding='utf-8')
        if result.returncode == 0:
            print("[OK] 成功")
            if result.stdout:
                print(result.stdout)
            return True
        else:
            print("[FAIL] 失败")
            if result.stderr:
                print(f"错误: {result.stderr}")
            if result.stdout:
                print(f"输出: {result.stdout}")
            return False
    except Exception as e:
        print(f"[FAIL] 异常: {e}")
        return False


def build_exe():
    """执行打包"""
    print("=" * 60)
    print(f"               {APP_NAME} EXE 打包工具")
    print("=" * 60)
    print()

    # 获取项目根目录
    project_root = PROJECT_ROOT
    os.chdir(project_root)
    print(f"工作目录: {project_root}")

    # 检查必要文件
    required_files = ["version_manager.py", "file_manager.py", "gui.py", "main.py"]
    missing_files = []
    for file in required_files:
        if not Path(file).exists():
            missing_files.append(file)

    if missing_files:
        print(f"错误: 缺少必要文件: {', '.join(missing_files)}")
        return False

    # 清理之前的构建
    print("\n1. 清理之前的构建...")
    dirs_to_clean = ["build", "dist", "__pycache__", "VersionManager.spec", "version_info.txt"]
    for item in dirs_to_clean:
        path = Path(item)
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
                print(f"  - 删除目录: {item}")
            else:
                path.unlink()
                print(f"  - 删除文件: {item}")

    # 安装PyInstaller（如果需要）
    print("\n2. 检查依赖...")

    # 检查PyInstaller
    try:
        import PyInstaller
        print(f"  - PyInstaller已安装: {PyInstaller.__version__}")
    except ImportError:
        print("  - 正在安装PyInstaller...")
        if not run_command(f'"{sys.executable}" -m pip install pyinstaller', "安装PyInstaller"):
            return False

    # 创建spec文件
    print("\n3. 创建打包配置...")
    datas = []
    version_parts = tuple(int(part) for part in APP_VERSION_NUMBER.split(".")) + (0,)
    version_info_content = f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={version_parts},
    prodvers={version_parts},
    mask=0x3F,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', 'Version Manager Team'),
          StringStruct('FileDescription', '{APP_NAME}'),
          StringStruct('FileVersion', '{APP_VERSION_NUMBER}'),
          StringStruct('InternalName', 'VersionManager'),
          StringStruct('OriginalFilename', 'VersionManager.exe'),
          StringStruct('ProductName', '{APP_NAME}'),
          StringStruct('ProductVersion', '{APP_VERSION_NUMBER}')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)"""
    with open("version_info.txt", "w", encoding="utf-8") as f:
        f.write(version_info_content)

    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas={datas},
    hiddenimports=[
        'sqlite3',
        'tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
        'tkinter.filedialog',
        'tkinter.scrolledtext',
        'tkinter.simpledialog',
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='VersionManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    version='version_info.txt',
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
'''

    with open("VersionManager.spec", "w", encoding="utf-8") as f:
        f.write(spec_content)
    print(f"  - VersionManager.spec 已创建 ({APP_DISPLAY_VERSION})")

    # 执行打包
    print("\n4. 开始打包...")
    if not run_command(f'"{sys.executable}" -m PyInstaller VersionManager.spec', "PyInstaller打包"):
        return False

    # 检查结果
    exe_path = Path("dist/VersionManager.exe")
    if exe_path.exists():
        file_size = exe_path.stat().st_size / (1024 * 1024)
        print(f"\n[OK] 打包成功!")
        print(f"  文件位置: {exe_path.absolute()}")
        print(f"  文件大小: {file_size:.1f} MB")
        return True
    else:
        print("\n[FAIL] 打包失败: 未找到输出文件")
        return False


def main():
    """主函数"""
    try:
        success = build_exe()

        print("\n" + "=" * 60)
        if success:
            print("打包完成！")
            print("\n使用说明:")
            print("1. 双击 dist/VersionManager.exe 启动程序")
            print("2. 运行 script/install_exe_menu.bat 安装右键菜单")
            print("3. 在文件夹上右键选择'使用VerMan版本管理'")

            # 询问是否立即安装右键菜单
            print()
            choice = input("是否立即安装右键菜单? (y/n): ").lower().strip()
            if choice in ['y', 'yes', '是', '']:
                print("\n正在安装右键菜单...")
                try:
                    subprocess.run([sys.executable, "script/install_exe_context_menu.py"], check=True)
                    print("右键菜单安装完成！")
                except subprocess.CalledProcessError as e:
                    print(f"右键菜单安装失败: {e}")
                    print("请手动运行 script/install_exe_menu.bat")
        else:
            print("打包失败，请检查错误信息")

        print("\n按回车键退出...")
        input()

    except KeyboardInterrupt:
        print("\n\n用户取消操作")
    except Exception as e:
        print(f"\n打包过程出现异常: {e}")
        print("按回车键退出...")
        input()


if __name__ == "__main__":
    main()
