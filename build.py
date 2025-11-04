"""
构建脚本 - 用于打包和分发 SVNLite
"""
import os
import sys
import shutil
import subprocess
import platform
from pathlib import Path


class Builder:
    """构建类"""

    def __init__(self):
        self.project_root = Path(__file__).parent
        self.build_dir = self.project_root / "build"
        self.dist_dir = self.project_root / "dist"
        self.current_platform = platform.system().lower()

    def clean_build(self):
        """清理构建目录"""
        print("清理构建目录...")
        for directory in [self.build_dir, self.dist_dir]:
            if directory.exists():
                shutil.rmtree(directory)
            directory.mkdir(parents=True, exist_ok=True)
        print("✅ 构建目录已清理")

    def install_dependencies(self):
        """安装构建依赖"""
        print("安装构建依赖...")
        dependencies = [
            "pyinstaller>=5.0.0",
            "setuptools>=61.0",
            "wheel"
        ]

        for dep in dependencies:
            print(f"  安装 {dep}...")
            subprocess.run([sys.executable, "-m", "pip", "install", dep], check=True)

        print("✅ 依赖安装完成")

    def build_executable(self):
        """构建可执行文件"""
        print("构建可执行文件...")

        # PyInstaller 配置
        pyinstaller_args = [
            "--name=SVNLite",
            "--windowed",  # 无控制台窗口
            "--onefile",   # 单文件模式
            "--icon=resources/icon.ico" if os.path.exists("resources/icon.ico") else "",
            "--add-data=svnlite/gui;svnlite/gui",
            "--hidden-import=PyQt6.QtCore",
            "--hidden-import=PyQt6.QtGui",
            "--hidden-import=PyQt6.QtWidgets",
            "--exclude-module=tkinter",
            "--exclude-module=matplotlib",
            "--exclude-module=numpy",
            "--exclude-module=pandas",
            f"--distpath={self.dist_dir}",
            f"--workpath={self.build_dir}",
            "main.py"
        ]

        # 移除空参数
        pyinstaller_args = [arg for arg in pyinstaller_args if arg]

        try:
            subprocess.run([sys.executable, "-m", "PyInstaller"] + pyinstaller_args, check=True)
            print("✅ 可执行文件构建成功")
        except subprocess.CalledProcessError as e:
            print(f"❌ 构建失败: {e}")
            return False

        return True

    def create_installer(self):
        """创建安装程序"""
        print("创建安装程序...")

        if self.current_platform == "windows":
            self.create_windows_installer()
        elif self.current_platform == "darwin":
            self.create_macos_installer()
        elif self.current_platform == "linux":
            self.create_linux_installer()
        else:
            print(f"⚠️  不支持的平台: {self.current_platform}")

    def create_windows_installer(self):
        """创建 Windows 安装程序"""
        print("创建 Windows 安装程序...")

        # 创建 NSIS 脚本
        nsis_script = f"""
!define APP_NAME "SVNLite"
!define APP_VERSION "0.1.0"
!define APP_PUBLISHER "SVNLite Team"
!define APP_URL "https://github.com/svnlite/svnlite"
!define APP_EXECUTABLE "SVNLite.exe"

Name "${{APP_NAME}}"
OutFile "${{self.dist_dir}}\\SVNLite-Setup-${{APP_VERSION}}.exe"
InstallDir "$PROGRAMFILES\\${{APP_NAME}}"
RequestExecutionLevel admin

Page directory
Page instfiles

Section "MainSection" SEC01
    SetOutPath "$INSTDIR"
    File "${{self.dist_dir}}\\${{APP_EXECUTABLE}}"
    CreateDirectory "$SMPROGRAMS\\${{APP_NAME}}"
    CreateShortCut "$SMPROGRAMS\\${{APP_NAME}}\\${{APP_NAME}}.lnk" "$INSTDIR\\${{APP_EXECUTABLE}}"
    CreateShortCut "$DESKTOP\\${{APP_NAME}}.lnk" "$INSTDIR\\${{APP_EXECUTABLE}}"
SectionEnd

Section "Uninstall"
    Delete "$INSTDIR\\${{APP_EXECUTABLE}}"
    Delete "$SMPROGRAMS\\${{APP_NAME}}\\${{APP_NAME}}.lnk"
    Delete "$DESKTOP\\${{APP_NAME}}.lnk"
    RMDir "$SMPROGRAMS\\${{APP_NAME}}"
    RMDir "$INSTDIR"
SectionEnd
        """

        nsis_file = self.build_dir / "installer.nsi"
        with open(nsis_file, 'w', encoding='utf-8') as f:
            f.write(nsis_script)

        # 尝试使用 NSIS 编译
        try:
            subprocess.run(["makensis", str(nsis_file)], check=True)
            print("✅ Windows 安装程序创建成功")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("⚠️  NSIS 未找到，跳过安装程序创建")
            print("  请手动安装 NSIS 或使用其他打包工具")

    def create_macos_installer(self):
        """创建 macOS 安装程序"""
        print("创建 macOS 安装程序...")

        # 创建 .app 包
        app_dir = self.dist_dir / "SVNLite.app"
        contents_dir = app_dir / "Contents"
        macos_dir = contents_dir / "MacOS"
        resources_dir = contents_dir / "Resources"

        # 创建目录结构
        for directory in [contents_dir, macos_dir, resources_dir]:
            directory.mkdir(parents=True, exist_ok=True)

        # 创建 Info.plist
        info_plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDisplayName</key>
    <string>SVNLite</string>
    <key>CFBundleExecutable</key>
    <string>SVNLite</string>
    <key>CFBundleIconFile</key>
    <string>icon.icns</string>
    <key>CFBundleIdentifier</key>
    <string>com.svnlite.app</string>
    <key>CFBundleName</key>
    <string>SVNLite</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>0.1.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
</dict>
</plist>"""

        with open(contents_dir / "Info.plist", 'w', encoding='utf-8') as f:
            f.write(info_plist)

        # 复制可执行文件
        executable = self.dist_dir / "SVNLite"
        if executable.exists():
            shutil.copy2(executable, macos_dir / "SVNLite")
            os.chmod(macos_dir / "SVNLite", 0o755)

        print("✅ macOS .app 包创建成功")

    def create_linux_installer(self):
        """创建 Linux 安装程序"""
        print("创建 Linux 安装程序...")

        # 创建 AppImage
        appdir = self.build_dir / "SVNLite.AppDir"
        appdir.mkdir(parents=True, exist_ok=True)

        # 复制可执行文件
        executable = self.dist_dir / "SVNLite"
        if executable.exists():
            shutil.copy2(executable, appdir / "SVNLite")
            os.chmod(appdir / "SVNLite", 0o755)

        # 创建桌面文件
        desktop_entry = """[Desktop Entry]
Type=Application
Name=SVNLite
Comment=轻量级本地文件版本管理系统
Exec=SVNLite
Icon=SVNLite
Categories=Development;VersionControl;"""

        with open(appdir / "SVNLite.desktop", 'w', encoding='utf-8') as f:
            f.write(desktop_entry)

        print("✅ Linux AppDir 创建成功")
        print("  可以使用 appimagetool 创建 AppImage")

    def create_portable_package(self):
        """创建便携包"""
        print("创建便携包...")

        portable_dir = self.dist_dir / "SVNLite-Portable"
        portable_dir.mkdir(exist_ok=True)

        # 复制可执行文件
        executable_name = "SVNLite.exe" if self.current_platform == "windows" else "SVNLite"
        executable = self.dist_dir / executable_name
        if executable.exists():
            shutil.copy2(executable, portable_dir / executable_name)

        # 创建启动脚本（Linux/macOS）
        if self.current_platform in ["linux", "darwin"]:
            start_script = f"""#!/bin/bash
cd "$(dirname "$0")"
./{executable_name}
"""
            with open(portable_dir / "start.sh", 'w', encoding='utf-8') as f:
                f.write(start_script)
            os.chmod(portable_dir / "start.sh", 0o755)

        # 创建说明文件
        readme_content = f"""SVNLite 便携版 v0.1.0
========================

SVNLite 是一个轻量级本地文件版本管理系统，无需服务器即可使用。

使用方法：
1. 直接运行 {executable_name}
2. 或在 Linux/macOS 上运行 start.sh

功能特性：
• 无服务器部署，本地文件存储
• 可视化操作，无需命令行
• 文件追踪、版本提交、历史查询
• 差异对比、版本回滚、备份管理

系统要求：
• Windows 10+ / macOS 10.15+ / Linux (Ubuntu 20.04+)
• Python 3.8+ (打包版本已包含)

更多信息请访问：https://github.com/svnlite/svnlite
"""

        with open(portable_dir / "README.txt", 'w', encoding='utf-8') as f:
            f.write(readme_content)

        # 创建压缩包
        archive_name = f"SVNLite-Portable-{self.current_platform}"
        if self.current_platform == "windows":
            archive_file = self.dist_dir / f"{archive_name}.zip"
            shutil.make_archive(str(archive_file.with_suffix('')), 'zip', portable_dir)
        else:
            archive_file = self.dist_dir / f"{archive_name}.tar.gz"
            shutil.make_archive(str(archive_file.with_suffix('')), 'gztar', portable_dir)

        print(f"✅ 便携包创建成功: {archive_file}")

    def run_tests(self):
        """运行测试"""
        print("运行测试...")
        test_files = [
            "tests/test_core.py",
            "tests/performance_test.py"
        ]

        for test_file in test_files:
            if os.path.exists(test_file):
                print(f"  运行 {test_file}...")
                try:
                    subprocess.run([sys.executable, test_file], check=True)
                    print(f"  ✅ {test_file} 通过")
                except subprocess.CalledProcessError:
                    print(f"  ❌ {test_file} 失败")
                    return False
            else:
                print(f"  ⚠️  {test_file} 不存在")

        print("✅ 所有测试完成")
        return True

    def build_all(self, run_tests_first=True):
        """执行完整构建流程"""
        print("开始构建 SVNLite...")
        print("=" * 50)

        # 运行测试
        if run_tests_first:
            if not self.run_tests():
                print("❌ 测试失败，停止构建")
                return False

        # 清理环境
        self.clean_build()

        # 安装依赖
        self.install_dependencies()

        # 构建可执行文件
        if not self.build_executable():
            print("❌ 构建失败")
            return False

        # 创建便携包
        self.create_portable_package()

        # 创建安装程序
        self.create_installer()

        print("\n" + "=" * 50)
        print("✅ 构建完成！")
        print(f"构建产物位于: {self.dist_dir}")

        # 列出构建产物
        if self.dist_dir.exists():
            print("\n构建产物:")
            for file in self.dist_dir.iterdir():
                size = file.stat().st_size / 1024 / 1024  # MB
                print(f"  {file.name} ({size:.1f}MB)")

        return True


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="SVNLite 构建脚本")
    parser.add_argument("--no-tests", action="store_true", help="跳过测试")
    parser.add_argument("--clean-only", action="store_true", help="仅清理构建目录")
    parser.add_argument("--portable-only", action="store_true", help="仅创建便携包")

    args = parser.parse_args()

    builder = Builder()

    if args.clean_only:
        builder.clean_build()
        return

    if args.portable_only:
        builder.clean_build()
        builder.install_dependencies()
        if builder.build_executable():
            builder.create_portable_package()
        return

    # 完整构建
    success = builder.build_all(run_tests_first=not args.no_tests)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()