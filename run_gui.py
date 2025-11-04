#!/usr/bin/env python
"""
启动SVNLite GUI应用
"""
import sys
import os
from pathlib import Path

# 添加src目录到Python路径
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# 检查PyQt6是否可用
try:
    from PyQt6.QtWidgets import QApplication
    print("PyQt6 found")
except ImportError:
    print("ERROR: PyQt6 not found. Please install it with:")
    print("uv add PyQt6")
    sys.exit(1)

# 尝试导入SVNLite
try:
    from svnlite.main import main
    print("SVNLite imported successfully")
except ImportError as e:
    print(f"ERROR: Failed to import SVNLite: {e}")
    print("Please check the installation.")
    sys.exit(1)

if __name__ == "__main__":
    print("Starting SVNLite GUI...")
    try:
        main()
    except Exception as e:
        print(f"ERROR: Failed to start SVNLite: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)