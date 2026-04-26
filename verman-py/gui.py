"""
Tkinter GUI for VerMan.
"""

import concurrent.futures
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Callable, List, Optional

from app_assets import get_asset_path
from app_info import APP_DISPLAY_VERSION, APP_ICON_ICO, APP_ICON_PNG, APP_NAME
from config import config_manager
from dialogs import VersionCompareDialog, VersionDetailsDialog
from logger import operation_logger
from models import CreateVersionResult, RollbackResult, ScanSnapshot
from project_manager import ProjectManager
from project_paths import is_project_workspace
from runtime_paths import find_packaged_executable
from version_manager import VersionManager


class VersionManagerGUI:
    """Main desktop application window."""

    def __init__(self, startup_path: Optional[str] = None):
        self.root = tk.Tk()
        self.root.title("VerMan - 版本管理工具")
        self.root.geometry(config_manager.get_window_geometry() or "900x600")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._window_icon_image: Optional[tk.PhotoImage] = None
        self._status_icon_image: Optional[tk.PhotoImage] = None
        self._apply_app_icon()

        self.project_manager = ProjectManager()
        self.version_manager: Optional[VersionManager] = None
        self.current_scan_snapshot: Optional[ScanSnapshot] = None
        self.current_changes = []
        self.all_versions = []

        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self._active_future: Optional[concurrent.futures.Future] = None
        self._busy_message = ""
        self._cleaned_up = False

        self._create_menu()
        self._create_widgets()
        self._create_status_bar()
        self._update_recent_projects_menu()
        self._update_ui_state()

        if startup_path:
            self.root.after(100, lambda: self._handle_startup_path(startup_path))

    def _create_menu(self):
        self.menubar = tk.Menu(self.root)
        self.root.config(menu=self.menubar)

        project_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="项目", menu=project_menu)
        project_menu.add_command(label="新建项目", command=self._new_project)
        project_menu.add_command(label="打开项目", command=self._open_project)
        self.recent_menu = tk.Menu(project_menu, tearoff=0)
        project_menu.add_cascade(label="最近项目", menu=self.recent_menu)
        project_menu.add_separator()
        project_menu.add_command(label="关闭项目", command=self._close_project)
        project_menu.add_separator()
        project_menu.add_command(label="删除项目", command=self._delete_project)
        project_menu.add_separator()
        project_menu.add_command(label="退出", command=self._on_close)

        version_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="版本", menu=version_menu)
        version_menu.add_command(label="提交版本", command=self._commit_version)
        version_menu.add_command(label="回滚版本", command=self._rollback_version)
        version_menu.add_separator()
        version_menu.add_command(label="导出版本", command=self._export_version)
        version_menu.add_command(label="比较版本", command=self._compare_versions)

        settings_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="设置", menu=settings_menu)
        settings_menu.add_command(label="配置设置", command=self._show_settings)
        settings_menu.add_separator()
        settings_menu.add_command(label="右键菜单管理", command=self._manage_context_menu)

        log_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="日志", menu=log_menu)
        log_menu.add_command(label="查看操作日志", command=self._show_operation_logs)
        log_menu.add_separator()
        log_menu.add_command(label="清空日志", command=self._clear_logs)

        help_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="帮助", menu=help_menu)
        help_menu.add_command(label="关于", command=self._show_about)

    def _create_widgets(self):
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        self.project_info_frame = ttk.LabelFrame(left_frame, text="项目信息")
        self.project_info_frame.pack(fill=tk.X, pady=(0, 5))
        self.project_path_label = ttk.Label(self.project_info_frame, text="未打开项目")
        self.project_path_label.pack(anchor=tk.W, padx=5, pady=2)

        changes_frame = ttk.LabelFrame(left_frame, text="文件变更")
        changes_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("状态", "文件路径")
        self.changes_tree = ttk.Treeview(changes_frame, columns=columns, show="headings", height=10)
        self.changes_tree.heading("状态", text="状态")
        self.changes_tree.heading("文件路径", text="文件路径")
        self.changes_tree.column("状态", width=80, anchor=tk.CENTER)
        self.changes_tree.column("文件路径", width=320, anchor=tk.W)

        changes_scrollbar = ttk.Scrollbar(changes_frame, orient=tk.VERTICAL, command=self.changes_tree.yview)
        self.changes_tree.configure(yscrollcommand=changes_scrollbar.set)
        self.changes_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        changes_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))

        versions_frame = ttk.LabelFrame(right_frame, text="版本历史")
        versions_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        version_columns = ("版本号", "时间", "描述", "变更数")
        self.versions_tree = ttk.Treeview(
            versions_frame,
            columns=version_columns,
            show="headings",
            height=10,
        )
        self.versions_tree.heading("版本号", text="版本号")
        self.versions_tree.heading("时间", text="创建时间")
        self.versions_tree.heading("描述", text="描述")
        self.versions_tree.heading("变更数", text="变更数")
        self.versions_tree.column("版本号", width=100, anchor=tk.CENTER)
        self.versions_tree.column("时间", width=140, anchor=tk.CENTER)
        self.versions_tree.column("描述", width=300, anchor=tk.W)
        self.versions_tree.column("变更数", width=100, anchor=tk.CENTER)

        versions_scrollbar = ttk.Scrollbar(versions_frame, orient=tk.VERTICAL, command=self.versions_tree.yview)
        self.versions_tree.configure(yscrollcommand=versions_scrollbar.set)
        self.versions_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        versions_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.versions_tree.bind("<Double-Button-1>", self._on_version_double_click)
        self.versions_tree.bind("<Button-3>", self._on_version_right_click)
        self.versions_tree.bind("<<TreeviewSelect>>", self._on_version_select)

        buttons_frame = ttk.Frame(right_frame)
        buttons_frame.pack(fill=tk.X)

        self.commit_button = ttk.Button(buttons_frame, text="提交版本", command=self._commit_version)
        self.commit_button.pack(side=tk.LEFT, padx=(0, 5))

        self.rollback_button = ttk.Button(
            buttons_frame, text="回滚选中版本", command=self._rollback_version
        )
        self.rollback_button.pack(side=tk.LEFT, padx=5)

        self.refresh_button = ttk.Button(buttons_frame, text="刷新", command=self._refresh_data)
        self.refresh_button.pack(side=tk.RIGHT)

    def _create_status_bar(self):
        self.status_frame = ttk.Frame(self.root)
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=2)

        self.status_icon_label = ttk.Label(self.status_frame, image=self._status_icon_image)
        self.status_icon_label.pack(side=tk.LEFT, padx=(0, 6))

        self.status_label = ttk.Label(self.status_frame, text="就绪", relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.db_status_label = ttk.Label(self.status_frame, text="数据库: 未连接", relief=tk.SUNKEN)
        self.db_status_label.pack(side=tk.RIGHT, padx=(5, 0))

    def _apply_app_icon(self):
        try:
            icon_png_path = get_asset_path(APP_ICON_PNG)
            if icon_png_path.exists():
                self._window_icon_image = tk.PhotoImage(file=str(icon_png_path))
                self.root.iconphoto(True, self._window_icon_image)

                subsample_factor = max(1, self._window_icon_image.width() // 16)
                self._status_icon_image = self._window_icon_image.subsample(
                    subsample_factor,
                    subsample_factor,
                )

            icon_ico_path = get_asset_path(APP_ICON_ICO)
            if sys.platform == "win32" and icon_ico_path.exists():
                self.root.iconbitmap(default=str(icon_ico_path))
        except Exception:
            self._window_icon_image = None
            self._status_icon_image = None

    def _ensure_not_busy(self) -> bool:
        if self._active_future is not None:
            messagebox.showinfo("请稍候", "正在执行操作，请等待完成。")
            return False
        return True

    def _run_task(
        self,
        status_message: str,
        task: Callable[[], object],
        on_success: Optional[Callable[[object], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ):
        if self._active_future is not None:
            messagebox.showinfo("请稍候", "正在执行操作，请等待完成。")
            return

        self._busy_message = status_message
        self._active_future = self._executor.submit(task)
        self._update_ui_state()

        def poll_future():
            if self._active_future is None:
                return
            if not self._active_future.done():
                self.root.after(100, poll_future)
                return

            future = self._active_future
            self._active_future = None
            self._busy_message = ""
            self._update_ui_state()

            try:
                result = future.result()
            except Exception as exc:
                if on_error:
                    on_error(str(exc))
                else:
                    messagebox.showerror("错误", str(exc))
                return

            if on_success:
                on_success(result)

        self.root.after(100, poll_future)

    def _update_ui_state(self):
        has_project = self.project_manager.is_project_open()
        is_busy = self._active_future is not None

        if has_project:
            project_path = self.project_manager.get_current_project_path()
            self.project_path_label.config(text=f"项目路径: {project_path}")
            self.db_status_label.config(text="数据库: 已连接")
        else:
            self.project_path_label.config(text="未打开项目")
            self.db_status_label.config(text="数据库: 未连接")

        self.commit_button.config(state=tk.DISABLED if is_busy or not has_project else tk.NORMAL)
        self.refresh_button.config(state=tk.DISABLED if is_busy or not has_project else tk.NORMAL)
        self.rollback_button.config(
            state=tk.DISABLED
            if is_busy or not has_project or not self.versions_tree.selection()
            else tk.NORMAL
        )

        if is_busy:
            self.status_label.config(text=self._busy_message)
            return

        if has_project:
            self.status_label.config(
                text=f"变更文件: {len(self.current_changes)} | 版本数: {len(self.all_versions)}"
            )
        else:
            self.status_label.config(text="请先创建或打开项目")

    def _refresh_data(self, force: bool = True, show_blocked_dialog: bool = True):
        if not self.project_manager.is_project_open() or not self.version_manager:
            return
        if not self._ensure_not_busy():
            return

        def task():
            snapshot = self.version_manager.refresh_workspace(force=force)
            versions = self.version_manager.get_all_versions()
            return snapshot, versions

        def on_success(result):
            snapshot, versions = result
            self.current_scan_snapshot = snapshot
            self.current_changes = snapshot.changes
            self.all_versions = versions
            self._update_changes_tree()
            self._update_versions_tree()
            self._update_ui_state()

        self._run_task("正在刷新工作区...", task, on_success=on_success)

    def _update_changes_tree(self):
        for item in self.changes_tree.get_children():
            self.changes_tree.delete(item)

        status_map = {"add": "新增", "modify": "修改", "delete": "删除"}
        for change in self.current_changes:
            status_text = status_map.get(change["file_status"], change["file_status"])
            self.changes_tree.insert("", tk.END, values=(status_text, change["relative_path"]))

    def _update_versions_tree(self):
        for item in self.versions_tree.get_children():
            self.versions_tree.delete(item)

        for version in self.all_versions:
            self.versions_tree.insert(
                "",
                tk.END,
                values=(
                    version["version_number"],
                    version["create_time"],
                    version["description"] or "无描述",
                    version["change_count"],
                ),
            )

    def _new_project(self):
        if not self._ensure_not_busy():
            return

        workspace_path = filedialog.askdirectory(
            title="选择工作区目录",
            initialdir=os.getcwd(),
        )
        if workspace_path:
            self._create_project(workspace_path)

    def _create_project(self, workspace_path: str):
        new_manager = ProjectManager()
        if new_manager.create_project(workspace_path):
            self.project_manager.close_project()
            self.project_manager = new_manager
            operation_logger.log_project_created(workspace_path)
            config_manager.add_recent_project(workspace_path)
            self._update_recent_projects_menu()
            self.version_manager = VersionManager(
                self.project_manager.get_database_manager(),
                self.project_manager.get_file_manager(),
                config_manager,
            )
            self._refresh_data()
        else:
            new_manager.close_project()
            messagebox.showerror("错误", "项目创建失败，可能是目录不存在或已经是项目")
            operation_logger.log_error("创建项目", f"项目创建失败: {workspace_path}", workspace_path)

    def _open_project(self, workspace_path: Optional[str] = None):
        if not self._ensure_not_busy():
            return

        if workspace_path is None:
            workspace_path = filedialog.askdirectory(
                title="选择项目目录",
                initialdir=os.getcwd(),
            )
        if not workspace_path:
            return

        new_manager = ProjectManager()
        if new_manager.open_project(workspace_path):
            self.project_manager.close_project()
            self.project_manager = new_manager
            operation_logger.log_project_opened(workspace_path)
            config_manager.add_recent_project(workspace_path)
            self._update_recent_projects_menu()
            self.version_manager = VersionManager(
                self.project_manager.get_database_manager(),
                self.project_manager.get_file_manager(),
                config_manager,
            )
            self._refresh_data()
        else:
            new_manager.close_project()
            messagebox.showerror("错误", "项目打开失败，可能是目录不存在或不是有效的项目")
            operation_logger.log_error("打开项目", f"项目打开失败: {workspace_path}", workspace_path)

    def _close_project(self):
        if not self.project_manager.is_project_open():
            return
        if not self._ensure_not_busy():
            return

        if messagebox.askyesno("确认", "确定要关闭当前项目吗？"):
            project_path = self.project_manager.get_current_project_path()
            self.project_manager.close_project()
            self.version_manager = None
            self.current_scan_snapshot = None
            self.current_changes = []
            self.all_versions = []
            if project_path:
                operation_logger.log_project_closed(project_path)
            self._update_changes_tree()
            self._update_versions_tree()
            self._update_ui_state()

    def _delete_project(self):
        if not self._ensure_not_busy():
            return

        if not self.project_manager.is_project_open():
            workspace_path = filedialog.askdirectory(title="选择要删除的项目目录")
            if not workspace_path:
                return
        else:
            workspace_path = self.project_manager.get_current_project_path()

        if messagebox.askyesno(
            "确认删除",
            f"确定要删除项目吗？\n这将删除版本数据但不会删除工作文件。\n\n项目路径: {workspace_path}",
        ):
            if self.project_manager.delete_project(workspace_path):
                messagebox.showinfo("成功", "项目删除成功")
                self.version_manager = None
                self.current_scan_snapshot = None
                self.current_changes = []
                self.all_versions = []
                self._update_changes_tree()
                self._update_versions_tree()
                self._update_ui_state()
            else:
                messagebox.showerror("错误", "项目删除失败")

    def _commit_version(self):
        if not self.version_manager or not self._ensure_not_busy():
            return
        if not self.current_scan_snapshot:
            self._refresh_data()
            return
        if not self.current_changes:
            messagebox.showinfo("提示", "没有文件变更，无需提交版本")
            return

        description = self._show_version_description_dialog()
        if description is None:
            return
        description = description.strip()
        if not description:
            messagebox.showerror("错误", "版本描述不能为空")
            return

        def task():
            return self.version_manager.create_version(description, self.current_scan_snapshot)

        def on_success(result: CreateVersionResult):
            if not result.success:
                if result.error:
                    messagebox.showerror("错误", result.error)
                else:
                    messagebox.showerror("错误", "版本创建失败")
                return

            project_path = self.project_manager.get_current_project_path()
            operation_logger.log_version_created(
                result.version_number,
                description,
                result.change_count,
                project_path,
            )
            self._refresh_data(force=True, show_blocked_dialog=False)

        self._run_task("正在提交版本...", task, on_success=on_success)

    def _rollback_version(self):
        if not self.version_manager or not self._ensure_not_busy():
            return

        selected_version = self._get_selected_version()
        if not selected_version:
            messagebox.showinfo("提示", "请先选择要回滚的版本")
            return

        confirm_message = (
            f"确定要回滚到版本 {selected_version['version_number']} 吗？\n\n"
            "这将恢复工作区到该版本的状态。"
        )
        if not messagebox.askyesno("确认回滚", confirm_message):
            return

        default_backup = config_manager.is_auto_backup_enabled()
        backup_message = f"是否备份当前状态？\n(默认设置: {'是' if default_backup else '否'})"
        backup_current = messagebox.askyesno("备份", backup_message)

        def task():
            return self.version_manager.rollback_to_version(selected_version["id"], backup_current)

        def on_success(result: RollbackResult):
            if not result.success:
                messagebox.showerror("错误", result.error or "回滚失败")
                return

            project_path = self.project_manager.get_current_project_path()
            operation_logger.log_version_rollback(
                selected_version["version_number"],
                backup_current,
                project_path,
            )
            messagebox.showinfo(
                "成功",
                f"已成功回滚到版本 {selected_version['version_number']}\n"
                f"恢复文件: {result.restored_count}，删除文件: {result.removed_count}",
            )
            self._refresh_data(force=True, show_blocked_dialog=False)

        self._run_task("正在回滚版本...", task, on_success=on_success)

    def _export_version(self):
        if not self.version_manager or not self._ensure_not_busy():
            return

        selected_version = self._get_selected_version()
        if not selected_version:
            messagebox.showinfo("提示", "请先选择要导出的版本")
            return

        export_path = filedialog.askdirectory(title="选择导出目录")
        if not export_path:
            return

        def task():
            return self.version_manager.export_version(selected_version["id"], export_path)

        def on_success(success: bool):
            if success:
                project_path = self.project_manager.get_current_project_path()
                operation_logger.log_version_exported(
                    selected_version["version_number"],
                    export_path,
                    project_path,
                )
                messagebox.showinfo(
                    "成功",
                    f"版本 {selected_version['version_number']} 已导出到 {export_path}",
                )
            else:
                messagebox.showerror("错误", "导出失败")

        self._run_task("正在导出版本...", task, on_success=on_success)

    def _compare_versions(self):
        if not self.version_manager or not self._ensure_not_busy():
            return
        if len(self.all_versions) < 2:
            messagebox.showinfo("提示", "需要至少两个版本才能进行比较")
            return

        dialog = VersionCompareDialog(self.root, self.all_versions, self._run_version_compare)
        dialog.show()

    def _run_version_compare(
        self,
        version_id1: int,
        version_id2: int,
        on_success: Callable[[dict], None],
        on_error: Callable[[str], None],
    ):
        def task():
            return self.version_manager.compare_versions(version_id1, version_id2)

        self._run_task(
            "正在比较版本...",
            task,
            on_success=on_success,
            on_error=lambda error: on_error(f"版本比较失败: {error}"),
        )

    def _on_version_select(self, _event):
        self._update_ui_state()

    def _on_version_double_click(self, _event):
        self._show_version_details()

    def _show_version_details(self):
        if not self.version_manager:
            return

        selected_version = self._get_selected_version()
        if not selected_version:
            return

        version_details = self.version_manager.get_version_details(selected_version["id"])
        if not version_details:
            messagebox.showerror("错误", "获取版本详情失败")
            return

        dialog = VersionDetailsDialog(
            self.root,
            version_details,
            project_path=self.project_manager.get_current_project_path(),
        )
        dialog.show()

    def _on_version_right_click(self, event):
        if not self.version_manager:
            return

        item = self.versions_tree.identify("item", event.x, event.y)
        if not item:
            return

        self.versions_tree.selection_set(item)
        context_menu = tk.Menu(self.root, tearoff=0)
        context_menu.add_command(label="查看详情", command=self._show_version_details)
        context_menu.add_separator()
        context_menu.add_command(label="导出版本", command=self._export_version)
        context_menu.add_command(label="回滚版本", command=self._rollback_version)
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()

    def _update_recent_projects_menu(self):
        self.recent_menu.delete(0, tk.END)
        recent_projects = config_manager.get_recent_projects()
        if not recent_projects:
            self.recent_menu.add_command(label="无最近项目", state=tk.DISABLED)
            return

        for index, project_path in enumerate(recent_projects, start=1):
            display_name = project_path if len(project_path) <= 50 else "..." + project_path[-47:]
            self.recent_menu.add_command(
                label=f"{index}. {display_name}",
                command=lambda path=project_path: self._open_project(path),
            )

    def _show_version_description_dialog(self) -> Optional[str]:
        class VersionDescriptionDialog(simpledialog.Dialog):
            def body(self, master):
                ttk.Label(master, text="请输入版本描述:").grid(row=0, column=0, padx=5, pady=5)
                self.text_widget = tk.Text(master, height=6, width=40)
                self.text_widget.grid(row=1, column=0, padx=5, pady=5, sticky="ew")
                scrollbar = ttk.Scrollbar(master, orient=tk.VERTICAL, command=self.text_widget.yview)
                scrollbar.grid(row=1, column=1, sticky="ns")
                self.text_widget.configure(yscrollcommand=scrollbar.set)
                self.text_widget.focus_set()
                return self.text_widget

            def apply(self):
                self.result = self.text_widget.get(1.0, tk.END).strip()

        dialog = VersionDescriptionDialog(self.root, "版本描述")
        return dialog.result

    def _show_settings(self):
        if not self._ensure_not_busy():
            return

        dialog = SettingsDialog(self.root, config_manager)
        self.root.wait_window(dialog.dialog)
        if self.project_manager.is_project_open():
            self._refresh_data(force=True, show_blocked_dialog=False)
        else:
            self._update_ui_state()

    def _manage_context_menu(self):
        if not self._ensure_not_busy():
            return

        dialog = ContextMenuManagerDialog(self.root)
        self.root.wait_window(dialog.dialog)

    def _show_about(self):
        about_text = (
            f"{APP_NAME} - 版本管理工具\n\n"
            "Windows 优先的本地文件版本管理工具。\n"
            "支持工作区扫描、版本快照、回滚、导出和版本比较。\n\n"
            f"版本: {APP_DISPLAY_VERSION}"
        )
        messagebox.showinfo("关于", about_text)

    def _show_operation_logs(self):
        if not self._ensure_not_busy():
            return

        dialog = LogViewerDialog(self.root)
        self.root.wait_window(dialog.dialog)

    def _clear_logs(self):
        if messagebox.askyesno("确认", "确定要清空所有操作日志吗？此操作无法撤销。"):
            try:
                operation_logger.clear_logs()
                messagebox.showinfo("成功", "日志已清空")
            except Exception as exc:
                messagebox.showerror("错误", f"清空日志失败: {exc}")

    def _get_selected_version(self) -> Optional[dict]:
        selected_items = self.versions_tree.selection()
        if not selected_items:
            return None
        version_number = self.versions_tree.item(selected_items[0])["values"][0]
        return next(
            (version for version in self.all_versions if version["version_number"] == version_number),
            None,
        )

    def _handle_startup_path(self, startup_path: str):
        candidate_path = os.path.abspath(startup_path)
        if os.path.isfile(candidate_path):
            candidate_path = os.path.dirname(candidate_path)

        if not os.path.isdir(candidate_path):
            messagebox.showerror("错误", f"启动路径不存在: {startup_path}")
            return

        if is_project_workspace(candidate_path):
            self._open_project(candidate_path)
            return

        if messagebox.askyesno(
            "创建项目",
            f"{candidate_path}\n\n这还不是 VerMan 项目，是否立即创建？",
        ):
            self._create_project(candidate_path)

    def _show_blocked_files_warning(self, blocked_files: List[object]):
        return

    def run(self):
        try:
            self.root.mainloop()
        finally:
            self._cleanup()

    def _on_close(self):
        if self._active_future is not None:
            messagebox.showinfo("请稍候", "正在执行操作，请等待完成。")
            return
        self.root.quit()

    def _cleanup(self):
        if self._cleaned_up:
            return
        self._cleaned_up = True

        try:
            if self.root.winfo_exists():
                try:
                    config_manager.set_window_geometry(self.root.geometry())
                except Exception:
                    pass

            self.project_manager.close_project()
            try:
                self._executor.shutdown(wait=False, cancel_futures=True)
            except TypeError:
                self._executor.shutdown(wait=False)
            if self.root.winfo_exists():
                self.root.destroy()
        except Exception:
            pass


class SettingsDialog:
    """Configuration dialog."""

    def __init__(self, parent, config_manager_instance):
        self.config_manager = config_manager_instance
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("设置")
        self.dialog.geometry("550x450")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (550 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (450 // 2)
        self.dialog.geometry(f"550x450+{x}+{y}")

        self._create_widgets()
        self._load_settings()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        config_frame = ttk.LabelFrame(main_frame, text="配置选项")
        config_frame.pack(fill=tk.X, pady=(0, 20))

        self.auto_backup_var = tk.BooleanVar()
        auto_backup_check = ttk.Checkbutton(
            config_frame,
            text="回滚时自动备份当前状态",
            variable=self.auto_backup_var,
        )
        auto_backup_check.pack(anchor=tk.W, padx=10, pady=5)

        ignore_frame = ttk.LabelFrame(main_frame, text="忽略文件模式")
        ignore_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

        ttk.Label(ignore_frame, text="每行一个文件模式 (支持 * 和 ? 通配符):").pack(
            anchor=tk.W, padx=10, pady=(10, 5)
        )

        list_frame = ttk.Frame(ignore_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.ignore_listbox = tk.Listbox(list_frame, height=8)
        ignore_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.ignore_listbox.yview)
        self.ignore_listbox.configure(yscrollcommand=ignore_scrollbar.set)
        self.ignore_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ignore_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        edit_frame = ttk.Frame(ignore_frame)
        edit_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.ignore_entry = ttk.Entry(edit_frame)
        self.ignore_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        small_button_style = {"padding": (8, 4)}
        ttk.Button(edit_frame, text="添加", command=self._add_ignore_pattern, width=8, **small_button_style).pack(
            side=tk.LEFT, padx=(5, 2)
        )
        ttk.Button(
            edit_frame,
            text="删除",
            command=self._remove_ignore_pattern,
            width=8,
            **small_button_style,
        ).pack(side=tk.LEFT, padx=2)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        button_style = {"padding": (10, 6)}
        ttk.Button(button_frame, text="确定", command=self._save_settings, **button_style).pack(
            side=tk.RIGHT, padx=(5, 0)
        )
        ttk.Button(button_frame, text="取消", command=self.dialog.destroy, **button_style).pack(side=tk.RIGHT)
        ttk.Button(button_frame, text="重置", command=self._reset_settings, **button_style).pack(
            side=tk.RIGHT, padx=(0, 5)
        )

    def _load_settings(self):
        self.auto_backup_var.set(self.config_manager.is_auto_backup_enabled())
        self.ignore_listbox.delete(0, tk.END)
        for pattern in self.config_manager.get_ignore_patterns():
            self.ignore_listbox.insert(tk.END, pattern)

    def _add_ignore_pattern(self):
        pattern = self.ignore_entry.get().strip()
        if pattern:
            self.ignore_listbox.insert(tk.END, pattern)
            self.ignore_entry.delete(0, tk.END)

    def _remove_ignore_pattern(self):
        selection = self.ignore_listbox.curselection()
        if selection:
            self.ignore_listbox.delete(selection[0])

    def _save_settings(self):
        try:
            self.config_manager.set_auto_backup(self.auto_backup_var.get())
            ignore_patterns = list(self.ignore_listbox.get(0, tk.END))
            self.config_manager.set_ignore_patterns(ignore_patterns)
            messagebox.showinfo("成功", "设置已保存")
            self.dialog.destroy()
        except Exception as exc:
            messagebox.showerror("错误", f"保存设置失败: {exc}")

    def _reset_settings(self):
        if messagebox.askyesno("确认", "确定要重置所有设置到默认值吗？"):
            self.config_manager.reset_to_defaults()
            self._load_settings()
            messagebox.showinfo("成功", "设置已重置")


class ContextMenuManagerDialog:
    """Install or uninstall the Windows Explorer context menu."""

    def __init__(self, parent):
        self.parent = parent
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("右键菜单管理")
        self.dialog.geometry("450x350")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (450 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (350 // 2)
        self.dialog.geometry(f"450x350+{x}+{y}")

        self._create_widgets()
        self._check_context_menu_status()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        status_frame = ttk.LabelFrame(main_frame, text="当前状态")
        status_frame.pack(fill=tk.X, pady=(0, 20))
        self.status_label = ttk.Label(status_frame, text="正在检查右键菜单状态...")
        self.status_label.pack(anchor=tk.W, padx=10, pady=10)

        info_frame = ttk.LabelFrame(main_frame, text="功能说明")
        info_frame.pack(fill=tk.X, pady=(0, 20))
        info_text = (
            "右键菜单功能可以让您在文件资源管理器中快速访问 VerMan：\n\n"
            "• 在文件夹上右键 -> 直接打开该文件夹的版本管理\n"
            "• 在文件夹空白处右键 -> 打开当前文件夹的版本管理\n"
            "• 在文件上右键 -> 打开文件所在文件夹的版本管理\n\n"
            "安装后将在 Windows 注册表中添加相应的右键菜单项。"
        )
        ttk.Label(info_frame, text=info_text, justify=tk.LEFT).pack(anchor=tk.W, padx=10, pady=10)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        button_style = {"padding": (10, 6)}
        self.install_button = ttk.Button(
            button_frame,
            text="安装右键菜单",
            command=self._install_context_menu,
            **button_style,
        )
        self.install_button.pack(side=tk.LEFT, padx=(0, 10))

        self.uninstall_button = ttk.Button(
            button_frame,
            text="卸载右键菜单",
            command=self._uninstall_context_menu,
            state=tk.DISABLED,
            **button_style,
        )
        self.uninstall_button.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(button_frame, text="刷新状态", command=self._check_context_menu_status, **button_style).pack(
            side=tk.LEFT
        )
        ttk.Button(button_frame, text="关闭", command=self.dialog.destroy, **button_style).pack(side=tk.RIGHT)

    def _check_context_menu_status(self):
        try:
            if sys.platform != "win32":
                self.status_label.config(text="错误: 当前系统不支持右键菜单功能", foreground="red")
                return

            import winreg

            registry_keys = [
                r"Directory\Background\shell\VerMan",
                r"Directory\shell\VerMan",
                r"*\shell\VerMan",
            ]

            installed_count = 0
            for key_path in registry_keys:
                try:
                    with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, key_path):
                        installed_count += 1
                except FileNotFoundError:
                    pass

            if installed_count == 3:
                self.status_label.config(text="✓ 右键菜单已安装 (全部3项)", foreground="green")
                self.install_button.config(state=tk.DISABLED)
                self.uninstall_button.config(state=tk.NORMAL)
            elif installed_count > 0:
                self.status_label.config(
                    text=f"⚠ 右键菜单部分安装 ({installed_count}/3项)",
                    foreground="orange",
                )
                self.install_button.config(state=tk.NORMAL)
                self.uninstall_button.config(state=tk.NORMAL)
            else:
                self.status_label.config(text="✗ 右键菜单未安装", foreground="red")
                self.install_button.config(state=tk.NORMAL)
                self.uninstall_button.config(state=tk.DISABLED)
        except Exception as exc:
            self.status_label.config(text=f"检查状态失败: {exc}", foreground="red")

    def _install_context_menu(self):
        try:
            if sys.platform != "win32":
                messagebox.showerror("错误", "当前系统不支持右键菜单功能")
                return

            exe_path = self._find_exe_path()
            if not exe_path:
                messagebox.showerror(
                    "错误",
                    "未找到 VersionManager.exe 文件\n请先运行 script/build_exe_simple.py 打包程序",
                )
                return

            success = self._install_context_menu_direct(exe_path)
            if success:
                messagebox.showinfo("成功", "右键菜单安装成功！")
                self._check_context_menu_status()
            else:
                messagebox.showerror("失败", "右键菜单安装失败")
        except Exception as exc:
            messagebox.showerror("错误", f"安装右键菜单失败: {exc}")

    def _find_exe_path(self) -> Optional[str]:
        return find_packaged_executable(search_roots=[Path(__file__).resolve().parent])

    def _install_context_menu_direct(self, exe_path: str) -> bool:
        try:
            import winreg

            with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, r"Directory\Background\shell\VerMan") as key:
                winreg.SetValueEx(key, None, 0, winreg.REG_SZ, "使用VerMan版本管理")
                with winreg.CreateKey(key, "command") as cmd_key:
                    winreg.SetValueEx(cmd_key, None, 0, winreg.REG_SZ, f'"{exe_path}" "%V"')

            with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, r"Directory\shell\VerMan") as key:
                winreg.SetValueEx(key, None, 0, winreg.REG_SZ, "使用VerMan版本管理")
                with winreg.CreateKey(key, "command") as cmd_key:
                    winreg.SetValueEx(cmd_key, None, 0, winreg.REG_SZ, f'"{exe_path}" "%1"')

            with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, r"*\shell\VerMan") as key:
                winreg.SetValueEx(key, None, 0, winreg.REG_SZ, "使用VerMan版本管理")
                with winreg.CreateKey(key, "command") as cmd_key:
                    winreg.SetValueEx(cmd_key, None, 0, winreg.REG_SZ, f'"{exe_path}" "%1"')

            return True
        except Exception as exc:
            messagebox.showerror("错误", f"安装注册表项失败: {exc}")
            return False

    def _uninstall_context_menu(self):
        try:
            if sys.platform != "win32":
                messagebox.showerror("错误", "当前系统不支持右键菜单功能")
                return

            if not messagebox.askyesno(
                "确认",
                "确定要卸载右键菜单吗？\n卸载后将无法通过右键菜单快速访问 VerMan。",
            ):
                return

            success = self._uninstall_context_menu_direct()
            if success:
                messagebox.showinfo("成功", "右键菜单卸载成功！")
                self._check_context_menu_status()
            else:
                messagebox.showerror("失败", "右键菜单卸载失败")
        except Exception as exc:
            messagebox.showerror("错误", f"卸载右键菜单失败: {exc}")

    def _uninstall_context_menu_direct(self) -> bool:
        try:
            import winreg

            registry_keys = [
                r"Directory\Background\shell\VerMan",
                r"Directory\shell\VerMan",
                r"*\shell\VerMan",
            ]
            for key_path in registry_keys:
                try:
                    winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, key_path + r"\command")
                except FileNotFoundError:
                    pass
                try:
                    winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, key_path)
                except FileNotFoundError:
                    pass
            return True
        except Exception as exc:
            messagebox.showerror("错误", f"删除注册表项失败: {exc}")
            return False


class LogViewerDialog:
    """Simple operation log viewer."""

    def __init__(self, parent):
        self.parent = parent
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("操作日志")
        self.dialog.geometry("800x500")
        self.dialog.resizable(True, True)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._center_dialog()
        self._create_widgets()
        self._load_logs()

    def _center_dialog(self):
        self.dialog.update_idletasks()
        dialog_width = self.dialog.winfo_width()
        dialog_height = self.dialog.winfo_height()

        parent_x = self.parent.winfo_rootx()
        parent_y = self.parent.winfo_rooty()
        parent_width = self.parent.winfo_width()
        parent_height = self.parent.winfo_height()

        x = parent_x + (parent_width // 2) - (dialog_width // 2)
        y = parent_y + (parent_height // 2) - (dialog_height // 2)
        self.dialog.geometry(f"{dialog_width}x{dialog_height}+{max(0, x)}+{max(0, y)}")

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(control_frame, text="筛选:").pack(side=tk.LEFT, padx=(0, 5))
        self.filter_var = tk.StringVar(value="全部")
        filter_combo = ttk.Combobox(
            control_frame,
            textvariable=self.filter_var,
            values=["全部", "INFO", "WARNING", "ERROR"],
            state="readonly",
            width=10,
        )
        filter_combo.pack(side=tk.LEFT, padx=(0, 10))
        filter_combo.bind("<<ComboboxSelected>>", self._filter_logs)

        ttk.Button(control_frame, text="刷新", command=self._load_logs).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(control_frame, text="清空日志", command=self._clear_logs).pack(side=tk.LEFT, padx=(0, 5))
        self.count_label = ttk.Label(control_frame, text="共 0 条日志")
        self.count_label.pack(side=tk.RIGHT)

        log_frame = ttk.Frame(main_frame)
        log_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("时间", "级别", "操作", "详情", "项目路径")
        self.log_tree = ttk.Treeview(log_frame, columns=columns, show="headings")
        for column, width, anchor in [
            ("时间", 140, tk.CENTER),
            ("级别", 80, tk.CENTER),
            ("操作", 120, tk.W),
            ("详情", 300, tk.W),
            ("项目路径", 200, tk.W),
        ]:
            self.log_tree.heading(column, text=column)
            self.log_tree.column(column, width=width, anchor=anchor)

        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_tree.yview)
        self.log_tree.configure(yscrollcommand=scrollbar.set)
        self.log_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(button_frame, text="关闭", command=self.dialog.destroy).pack(side=tk.RIGHT)

    def _load_logs(self):
        try:
            self.all_logs = operation_logger.get_logs()
            self._filter_logs()
        except Exception as exc:
            messagebox.showerror("错误", f"加载日志失败: {exc}")

    def _filter_logs(self, _event=None):
        try:
            for item in self.log_tree.get_children():
                self.log_tree.delete(item)

            filter_level = self.filter_var.get()
            if filter_level == "全部":
                filtered_logs = self.all_logs
            else:
                filtered_logs = [
                    log_entry for log_entry in self.all_logs if log_entry.get("level") == filter_level
                ]

            for log_entry in reversed(filtered_logs):
                tags = ()
                if log_entry.get("level") == "ERROR":
                    tags = ("error",)
                elif log_entry.get("level") == "WARNING":
                    tags = ("warning",)

                self.log_tree.insert(
                    "",
                    tk.END,
                    values=(
                        log_entry.get("timestamp", ""),
                        log_entry.get("level", ""),
                        log_entry.get("action", ""),
                        log_entry.get("details", ""),
                        log_entry.get("project_path", ""),
                    ),
                    tags=tags,
                )

            self.log_tree.tag_configure("error", foreground="red")
            self.log_tree.tag_configure("warning", foreground="orange")
            self.count_label.config(text=f"共 {len(filtered_logs)} 条日志")
        except Exception as exc:
            messagebox.showerror("错误", f"筛选日志失败: {exc}")

    def _clear_logs(self):
        if messagebox.askyesno("确认", "确定要清空所有操作日志吗？此操作无法撤销。"):
            try:
                operation_logger.clear_logs()
                self._load_logs()
                messagebox.showinfo("成功", "日志已清空")
            except Exception as exc:
                messagebox.showerror("错误", f"清空日志失败: {exc}")
