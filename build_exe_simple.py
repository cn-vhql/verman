"""
最简单的打包脚本
假设PyInstaller已经安装在系统中
"""

import subprocess
import sys
import os

def find_python_executable():
    """查找系统中的Python可执行文件"""
    # 尝试常见的Python路径
    python_paths = [
        "python",
        "python3",
        "py",
        "C:\\Python311\\python.exe",
        "C:\\Python310\\python.exe",
        "C:\\Python39\\python.exe",
        "C:\\Python38\\python.exe",
    ]

    for python_path in python_paths:
        try:
            result = subprocess.run([python_path, "--version"],
                                      capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return python_path
        except:
            continue

    return None

def build_exe():
    """构建exe文件"""
    python_exe = find_python_executable()

    if not python_exe:
        print("错误: 未找到Python可执行文件")
        print("请确保Python 3.8+已正确安装并添加到PATH环境变量")
        return False

    print(f"使用Python: {python_exe}")
    print(f"Python版本: {subprocess.run([python_exe, '--version'], capture_output=True, text=True).stdout.strip()}")

    # 检查PyInstaller
    try:
        result = subprocess.run([python_exe, "-m", "PyInstaller", "--version"],
                              capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            print("未找到PyInstaller，尝试安装...")
            install_cmd = [python_exe, "-m", "pip", "install", "pyinstaller"]
            try:
                subprocess.run(install_cmd, check=True)
                print("PyInstaller安装成功")
            except subprocess.CalledProcessError:
                print("PyInstaller安装失败，请手动安装后重试")
                print("运行命令: pip install pyinstaller")
                return False
    except:
        print("PyInstaller检查失败")

    # 打包
    print("开始打包VersionManager...")

    cmd = [
        python_exe,
        "-m",
        "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", "VersionManager",
        "--clean",
        "--noconfirm",
        "main.py"
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print("打包成功！")
            if os.path.exists("dist/VersionManager.exe"):
                file_size = os.path.getsize("dist/VersionManager.exe")
                print(f"可执行文件: dist/VersionManager.exe ({file_size // 1024} KB)")
            else:
                print("警告: exe文件未找到，检查打包日志")

            if result.stderr:
                print("警告信息:")
                print(result.stderr.strip())
            return True
        else:
            print("打包失败:")
            if result.stdout:
                print("输出:")
                print(result.stdout)
            if result.stderr:
                print("错误:")
                print(result.stderr)
            return False

    except Exception as e:
        print(f"打包错误: {e}")
        return False

if __name__ == "__main__":
    if not os.path.exists("main.py"):
        print("错误: 未找到main.py文件")
        print("请确保在项目根目录运行此脚本")
        sys.exit(1)

    print("=== VersionManager EXE 打包工具 ===\n")
    if build_exe():
        print("\n=== 打包成功 ===")
        print("文件位置: dist/VersionManager.exe")
        print("\n您现在可以:")
        print("1. 双击 VersionManager.exe 运行程序")
        print("2. 将exe文件复制到其他电脑")
        print("3. 创建桌面快捷方式")
    else:
        print("\n=== 打包失败 ===")
        print("请检查Python和PyInstaller是否正确安装")
        print("或者手动运行: pip install pyinstaller")
        print("然后运行: pyinstaller --onefile --windowed --name VersionManager main.py")

    input("\n按回车键退出...")