"""
本地文件版本管理工具主程序
"""

from gui import VersionManagerGUI


def main():
    """主函数"""
    app = VersionManagerGUI()
    app.run()


if __name__ == "__main__":
    main()
