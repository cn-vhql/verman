"""
SVNLite - 轻量级本地文件版本管理系统
主程序入口
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTranslator, QLocale
from .gui.main_window import MainWindow


def main():
    """主程序入口"""
    # 创建 QApplication
    app = QApplication(sys.argv)
    app.setApplicationName("SVNLite")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("SVNLite Team")

    # 设置应用图标
    # app.setWindowIcon(QIcon("resources/icon.png"))

    # 创建并显示主窗口
    window = MainWindow()
    window.show()

    # 运行事件循环
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
