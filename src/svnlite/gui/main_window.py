"""
主窗口界面
"""
import os
import sys
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QMenuBar, QToolBar, QStatusBar, QTabWidget, QTreeWidget, QTreeWidgetItem,
    QTextEdit, QLabel, QPushButton, QMessageBox, QFileDialog, QInputDialog,
    QComboBox, QLineEdit, QProgressBar, QFrame, QGroupBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from ..core.models import Repository, Config, FileStatus
from ..core.repository_manager import RepositoryManager
from ..core.file_tracker import FileTracker
from ..config.config_manager import ConfigManager
from ..storage.version_storage import VersionStorage


class MainWindow(QMainWindow):
    """主窗口类"""

    def __init__(self):
        super().__init__()
        self.current_repo_path = os.getcwd()
        self.repo_manager: Optional[RepositoryManager] = None
        self.file_tracker: Optional[FileTracker] = None
        self.config_manager: Optional[ConfigManager] = None
        self.storage: Optional[VersionStorage] = None

        self.init_ui()
        self.init_connections()
        self.check_repository()

    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("SVNLite - 轻量级本地文件版本管理系统")
        self.setGeometry(100, 100, 1000, 700)

        # 创建菜单栏
        self.create_menu_bar()

        # 创建工具栏
        self.create_toolbar()

        # 创建中央部件
        self.create_central_widget()

        # 创建状态栏
        self.create_status_bar()

        # 应用样式
        self.apply_styles()

    def create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()

        # 版本库菜单
        repo_menu = menubar.addMenu('版本库(&R)')

        init_action = repo_menu.addAction('初始化版本库(&I)')
        init_action.setShortcut('Ctrl+I')
        init_action.setStatusTip('在当前目录初始化版本库')
        init_action.triggered.connect(self.init_repository)

        open_action = repo_menu.addAction('打开版本库(&O)')
        open_action.setShortcut('Ctrl+O')
        open_action.setStatusTip('打开现有版本库')
        open_action.triggered.connect(self.open_repository)

        repo_menu.addSeparator()

        close_action = repo_menu.addAction('关闭版本库(&C)')
        close_action.setStatusTip('关闭当前版本库')
        close_action.triggered.connect(self.close_repository)

        # 文件菜单
        file_menu = menubar.addMenu('文件(&F)')

        add_action = file_menu.addAction('添加文件到追踪(&A)')
        add_action.setShortcut('Ctrl+A')
        add_action.setStatusTip('添加文件到追踪列表')
        add_action.triggered.connect(self.add_files)

        # 帮助菜单
        help_menu = menubar.addMenu('帮助(&H)')

        about_action = help_menu.addAction('关于(&A)')
        about_action.setStatusTip('关于SVNLite')
        about_action.triggered.connect(self.show_about)

    def create_toolbar(self):
        """创建工具栏"""
        toolbar = self.addToolBar('主工具栏')
        toolbar.setMovable(False)

        # 初始化版本库
        init_btn = QPushButton('初始化版本库')
        init_btn.clicked.connect(self.init_repository)
        toolbar.addWidget(init_btn)

        toolbar.addSeparator()

        # 添加文件
        add_btn = QPushButton('添加文件')
        add_btn.clicked.connect(self.add_files)
        toolbar.addWidget(add_btn)

        # 打开版本库
        open_btn = QPushButton('打开版本库')
        open_btn.clicked.connect(self.open_repository)
        toolbar.addWidget(open_btn)

        toolbar.addSeparator()

        # 刷新
        refresh_btn = QPushButton('刷新')
        refresh_btn.clicked.connect(self.refresh_all)
        toolbar.addWidget(refresh_btn)

    def create_central_widget(self):
        """创建中央部件"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QVBoxLayout(central_widget)

        # 状态显示
        self.status_label = QLabel('未初始化版本库')
        self.status_label.setStyleSheet("font-weight: bold; padding: 10px; background-color: #f0f0f0; border: 1px solid #ccc;")
        main_layout.addWidget(self.status_label)

        # 文件状态标签页
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # 文件列表
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(['文件名', '状态', '大小', '修改时间'])
        self.file_tree.setColumnWidth(0, 300)
        self.file_tree.setColumnWidth(1, 100)
        self.file_tree.setColumnWidth(2, 100)
        self.file_tree.setColumnWidth(3, 150)
        self.tab_widget.addTab(self.file_tree, "文件状态")

        # 日志显示
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        self.tab_widget.addTab(self.log_text, "操作日志")

    def create_status_bar(self):
        """创建状态栏"""
        self.status_bar = self.statusBar()

        # 版本信息
        self.version_label = QLabel('未初始化版本库')
        self.status_bar.addWidget(self.version_label)

        # 状态指示器
        self.status_indicator = QLabel()
        self.status_bar.addPermanentWidget(self.status_indicator)

    def apply_styles(self):
        """应用样式"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QTabWidget::pane {
                border: 1px solid #c0c0c0;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #e1e1e1;
                padding: 8px 16px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom: 2px solid #0078d4;
            }
            QTreeWidget {
                alternate-background-color: #f9f9f9;
                gridline-color: #e0e0e0;
            }
            QTreeWidget::item:selected {
                background-color: #0078d4;
                color: white;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QStatusBar {
                background-color: #f0f0f0;
                border-top: 1px solid #c0c0c0;
            }
        """)

    def init_connections(self):
        """初始化信号连接"""
        # 定时刷新
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.auto_refresh)
        self.refresh_timer.start(30000)  # 30秒刷新一次

    def check_repository(self):
        """检查当前目录是否为版本库"""
        if os.path.exists(os.path.join(self.current_repo_path, '.svmini')):
            self.open_repository_path(self.current_repo_path)
        else:
            self.update_ui_for_no_repository()

    def open_repository_path(self, path: str):
        """打开指定路径的版本库"""
        try:
            self.current_repo_path = path
            repository = Repository(path)

            if not repository.is_repository():
                self.log_message(f"目录 {path} 不是有效的版本库")
                return

            # 初始化管理器
            self.repo_manager = RepositoryManager(path)
            self.config_manager = ConfigManager(path)
            self.storage = VersionStorage(repository)
            self.file_tracker = FileTracker(repository, self.repo_manager.ignore_rules)

            # 更新界面
            self.update_ui_for_repository()
            self.refresh_all()

            self.log_message(f"版本库已打开: {path}")

        except Exception as e:
            self.log_message(f"打开版本库失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"打开版本库失败:\n{str(e)}")

    def update_ui_for_repository(self):
        """更新界面为有版本库状态"""
        self.version_label.setText(f'版本库: {self.current_repo_path}')
        self.status_indicator.setText('●')
        self.status_indicator.setStyleSheet('color: green;')

    def update_ui_for_no_repository(self):
        """更新界面为无版本库状态"""
        self.version_label.setText('未初始化版本库')
        self.status_indicator.setText('●')
        self.status_indicator.setStyleSheet('color: red;')

        # 清空面板
        self.file_tree.clear()
        self.log_text.clear()

    def log_message(self, message: str):
        """添加日志消息"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")

    def refresh_all(self):
        """刷新所有显示"""
        if self.repo_manager and self.repo_manager.repository.is_repository():
            self.refresh_file_tree()
            self.log_message("刷新完成")

    def refresh_file_tree(self):
        """刷新文件树"""
        if not self.file_tracker:
            return

        self.file_tree.clear()

        try:
            file_status = self.file_tracker.scan_files()
            for relative_path, file_info in file_status.items():
                item = QTreeWidgetItem()
                item.setText(0, relative_path)
                item.setText(1, self.get_status_text(file_info.status))
                item.setText(2, self.format_size(file_info.size))
                item.setText(3, self.format_time(file_info.mtime))
                self.file_tree.addTopLevelItem(item)
        except Exception as e:
            self.log_message(f"刷新文件列表失败: {e}")

    def get_status_text(self, status: FileStatus) -> str:
        """获取状态文本"""
        status_map = {
            FileStatus.TRACKED: "已追踪",
            FileStatus.UNTRACKED: "未追踪",
            FileStatus.MODIFIED: "已修改",
            FileStatus.ADDED: "新增",
            FileStatus.DELETED: "已删除",
            FileStatus.UNCHANGED: "未改变"
        }
        return status_map.get(status, "未知")

    def format_size(self, size: int) -> str:
        """格式化文件大小"""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.1f} MB"

    def format_time(self, timestamp: float) -> str:
        """格式化时间"""
        from datetime import datetime
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")

    def auto_refresh(self):
        """自动刷新"""
        if self.repo_manager and self.repo_manager.repository.is_repository():
            self.refresh_all()

    # 菜单和工具栏操作方法
    def init_repository(self):
        """初始化版本库"""
        dir_path = QFileDialog.getExistingDirectory(
            self, "选择目录", self.current_repo_path
        )
        if dir_path:
            try:
                from ..core.models import Config
                config = Config(author=os.getenv('USERNAME', 'Unknown User'))

                repo_manager = RepositoryManager(dir_path)
                success, message = repo_manager.initialize_repository(config.author)

                if success:
                    self.open_repository_path(dir_path)
                    QMessageBox.information(self, "成功", message)
                else:
                    QMessageBox.warning(self, "警告", message)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"初始化失败:\n{str(e)}")

    def open_repository(self):
        """打开版本库"""
        dir_path = QFileDialog.getExistingDirectory(
            self, "选择版本库目录", self.current_repo_path
        )
        if dir_path:
            self.open_repository_path(dir_path)

    def close_repository(self):
        """关闭版本库"""
        self.repo_manager = None
        self.file_tracker = None
        self.config_manager = None
        self.storage = None
        self.update_ui_for_no_repository()
        self.log_message("版本库已关闭")

    def add_files(self):
        """添加文件到追踪"""
        if not self.file_tracker:
            QMessageBox.warning(self, "警告", "请先打开版本库")
            return

        files, _ = QFileDialog.getOpenFileNames(
            self, "选择要添加的文件", self.current_repo_path
        )
        if files:
            try:
                success, message, added_files = self.file_tracker.add_files(files)
                if success:
                    self.log_message(f"成功添加 {len(added_files)} 个文件到追踪")
                    self.refresh_all()
                else:
                    QMessageBox.warning(self, "警告", message)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"添加文件失败:\n{str(e)}")

    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self, "关于 SVNLite",
            "SVNLite v0.1.0\n\n"
            "轻量级本地文件版本管理系统\n"
            "基于 PyQt6 开发的图形界面版本控制工具\n\n"
            "特性:\n"
            "• 无服务器部署，本地文件存储\n"
            "• 可视化操作，无需命令行\n"
            "• 文件追踪、版本提交、历史查询\n"
            "• 差单易用的图形界面\n\n"
            "开发团队: SVNLite Team\n"
            f"Python版本: {sys.version.split()[0]}\n"
            f"平台: {sys.platform}"
        )

    def closeEvent(self, event):
        """窗口关闭事件"""
        event.accept()