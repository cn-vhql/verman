"""
图形用户界面模块
使用Tkinter实现简洁的版本管理界面
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import os
from typing import Optional, List
from project_manager import ProjectManager
from version_manager import VersionManager
from dialogs import VersionCompareDialog, VersionDetailsDialog
from config import config_manager


class VersionManagerGUI:
    """版本管理工具GUI"""

    def __init__(self):
        """初始化GUI"""
        self.root = tk.Tk()
        self.root.title("本地文件版本管理工具")
        self.root.geometry("900x600")

        # 项目管理器
        self.project_manager = ProjectManager()
        self.version_manager: Optional[VersionManager] = None

        # 创建界面
        self._create_menu()
        self._create_widgets()
        self._create_status_bar()

        # 界面状态
        self.current_changes = []
        self.all_versions = []

        # 初始化界面状态
        self._update_ui_state()

    def _create_menu(self):
        """创建菜单栏"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # 项目菜单
        project_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="项目", menu=project_menu)
        project_menu.add_command(label="新建项目", command=self._new_project)
        project_menu.add_command(label="打开项目", command=self._open_project)

        # 最近项目子菜单
        self.recent_menu = tk.Menu(project_menu, tearoff=0)
        project_menu.add_cascade(label="最近项目", menu=self.recent_menu)
        self._update_recent_projects_menu()

        project_menu.add_separator()
        project_menu.add_command(label="关闭项目", command=self._close_project)
        project_menu.add_separator()
        project_menu.add_command(label="删除项目", command=self._delete_project)
        project_menu.add_separator()
        project_menu.add_command(label="退出", command=self.root.quit)

        # 版本菜单
        version_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="版本", menu=version_menu)
        version_menu.add_command(label="提交版本", command=self._commit_version)
        version_menu.add_command(label="回滚版本", command=self._rollback_version)
        version_menu.add_separator()
        version_menu.add_command(label="导出版本", command=self._export_version)
        version_menu.add_command(label="比较版本", command=self._compare_versions)

        # 帮助菜单
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="帮助", menu=help_menu)
        help_menu.add_command(label="关于", command=self._show_about)

    def _create_widgets(self):
        """创建主要界面组件"""
        # 主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 左侧面板 - 项目信息和变更列表
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        # 项目信息
        self.project_info_frame = ttk.LabelFrame(left_frame, text="项目信息")
        self.project_info_frame.pack(fill=tk.X, pady=(0, 5))

        self.project_path_label = ttk.Label(self.project_info_frame, text="未打开项目")
        self.project_path_label.pack(anchor=tk.W, padx=5, pady=2)

        # 变更列表
        changes_frame = ttk.LabelFrame(left_frame, text="文件变更")
        changes_frame.pack(fill=tk.BOTH, expand=True)

        # 变更列表表格
        columns = ('状态', '文件路径')
        self.changes_tree = ttk.Treeview(changes_frame, columns=columns, show='headings', height=10)
        self.changes_tree.heading('状态', text='状态')
        self.changes_tree.heading('文件路径', text='文件路径')
        self.changes_tree.column('状态', width=80, anchor=tk.CENTER)
        self.changes_tree.column('文件路径', width=300, anchor=tk.W)

        # 滚动条
        changes_scrollbar = ttk.Scrollbar(changes_frame, orient=tk.VERTICAL, command=self.changes_tree.yview)
        self.changes_tree.configure(yscrollcommand=changes_scrollbar.set)

        self.changes_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        changes_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 右侧面板 - 版本列表
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))

        # 版本列表
        versions_frame = ttk.LabelFrame(right_frame, text="版本历史")
        versions_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        # 版本列表表格
        version_columns = ('版本号', '时间', '描述', '变更数')
        self.versions_tree = ttk.Treeview(versions_frame, columns=version_columns, show='headings', height=10)
        self.versions_tree.heading('版本号', text='版本号')
        self.versions_tree.heading('时间', text='创建时间')
        self.versions_tree.heading('描述', text='描述')
        self.versions_tree.heading('变更数', text='变更数')

        self.versions_tree.column('版本号', width=100, anchor=tk.CENTER)
        self.versions_tree.column('时间', width=140, anchor=tk.CENTER)
        self.versions_tree.column('描述', width=200, anchor=tk.W)
        self.versions_tree.column('变更数', width=80, anchor=tk.CENTER)

        # 版本列表滚动条
        versions_scrollbar = ttk.Scrollbar(versions_frame, orient=tk.VERTICAL, command=self.versions_tree.yview)
        self.versions_tree.configure(yscrollcommand=versions_scrollbar.set)

        self.versions_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        versions_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 版本列表绑定双击事件
        self.versions_tree.bind('<Double-Button-1>', self._on_version_double_click)

        # 操作按钮框架
        buttons_frame = ttk.Frame(right_frame)
        buttons_frame.pack(fill=tk.X)

        self.commit_button = ttk.Button(buttons_frame, text="提交版本", command=self._commit_version)
        self.commit_button.pack(side=tk.LEFT, padx=(0, 5))

        self.rollback_button = ttk.Button(buttons_frame, text="回滚选中版本", command=self._rollback_version)
        self.rollback_button.pack(side=tk.LEFT, padx=5)

        self.refresh_button = ttk.Button(buttons_frame, text="刷新", command=self._refresh_data)
        self.refresh_button.pack(side=tk.RIGHT)

    def _create_status_bar(self):
        """创建状态栏"""
        self.status_frame = ttk.Frame(self.root)
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=2)

        self.status_label = ttk.Label(self.status_frame, text="就绪", relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.db_status_label = ttk.Label(self.status_frame, text="数据库: 未连接", relief=tk.SUNKEN)
        self.db_status_label.pack(side=tk.RIGHT, padx=(5, 0))

    def _update_ui_state(self):
        """更新界面状态"""
        has_project = self.project_manager.is_project_open()

        # 更新项目信息
        if has_project:
            project_path = self.project_manager.get_current_project_path()
            self.project_path_label.config(text=f"项目路径: {project_path}")
            self.db_status_label.config(text="数据库: 已连接")
        else:
            self.project_path_label.config(text="未打开项目")
            self.db_status_label.config(text="数据库: 未连接")

        # 更新按钮状态
        self.commit_button.config(state=tk.NORMAL if has_project else tk.DISABLED)
        self.rollback_button.config(state=tk.NORMAL if has_project and self.versions_tree.selection() else tk.DISABLED)

        # 更新状态栏
        if has_project:
            change_count = len(self.current_changes)
            version_count = len(self.all_versions)
            self.status_label.config(text=f"变更文件: {change_count} | 版本数: {version_count}")
        else:
            self.status_label.config(text="请先创建或打开项目")

    def _refresh_data(self):
        """刷新数据"""
        if not self.project_manager.is_project_open():
            return

        try:
            # 清除缓存，确保获取最新状态
            if self.version_manager:
                self.version_manager._clear_scan_cache()
                if hasattr(self.version_manager.file_manager, 'clear_hash_cache'):
                    self.version_manager.file_manager.clear_hash_cache()

            # 刷新变更列表
            if self.version_manager:
                self.current_changes = self.version_manager.get_current_changes()
                self._update_changes_tree()

            # 刷新版本列表
            if self.version_manager:
                self.all_versions = self.version_manager.get_all_versions()
                self._update_versions_tree()

            # 更新界面状态
            self._update_ui_state()

        except Exception as e:
            messagebox.showerror("错误", f"刷新数据失败: {e}")

    def _update_changes_tree(self):
        """更新变更列表"""
        # 清空现有项
        for item in self.changes_tree.get_children():
            self.changes_tree.delete(item)

        # 添加变更项
        for change in self.current_changes:
            status_text = change['file_status'].upper()
            if status_text == 'ADD':
                status_text = '新增'
            elif status_text == 'MODIFY':
                status_text = '修改'
            elif status_text == 'DELETE':
                status_text = '删除'

            self.changes_tree.insert('', tk.END, values=(status_text, change['relative_path']))

    def _update_versions_tree(self):
        """更新版本列表"""
        # 清空现有项
        for item in self.versions_tree.get_children():
            self.versions_tree.delete(item)

        # 添加版本项
        for version in self.all_versions:
            self.versions_tree.insert('', tk.END, values=(
                version['version_number'],
                version['create_time'],
                version['description'] or '无描述',
                version['change_count']
            ))

    def _new_project(self):
        """新建项目"""
        # 选择工作区目录
        workspace_path = filedialog.askdirectory(title="选择工作区目录")
        if not workspace_path:
            return

        # 创建项目
        if self.project_manager.create_project(workspace_path):
            messagebox.showinfo("成功", "项目创建成功")
            # 添加到最近项目
            config_manager.add_recent_project(workspace_path)
            self._update_recent_projects_menu()

            self.version_manager = VersionManager(
                self.project_manager.get_database_manager(),
                self.project_manager.get_file_manager()
            )
            self._refresh_data()
        else:
            messagebox.showerror("错误", "项目创建失败，可能是目录不存在或已经是项目")

    def _open_project(self, workspace_path: str = None):
        """打开项目"""
        # 选择工作区目录
        if workspace_path is None:
            workspace_path = filedialog.askdirectory(title="选择项目目录")
        if not workspace_path:
            return

        # 打开项目
        if self.project_manager.open_project(workspace_path):
            messagebox.showinfo("成功", "项目打开成功")
            # 添加到最近项目
            config_manager.add_recent_project(workspace_path)
            self._update_recent_projects_menu()

            self.version_manager = VersionManager(
                self.project_manager.get_database_manager(),
                self.project_manager.get_file_manager()
            )
            self._refresh_data()
        else:
            messagebox.showerror("错误", "项目打开失败，可能是目录不存在或不是有效的项目")

    def _close_project(self):
        """关闭项目"""
        if not self.project_manager.is_project_open():
            return

        if messagebox.askyesno("确认", "确定要关闭当前项目吗？"):
            self.project_manager.close_project()
            self.version_manager = None
            self.current_changes = []
            self.all_versions = []

            # 清空界面
            self._update_changes_tree()
            self._update_versions_tree()
            self._update_ui_state()

    def _delete_project(self):
        """删除项目"""
        if not self.project_manager.is_project_open():
            # 选择要删除的项目目录
            workspace_path = filedialog.askdirectory(title="选择要删除的项目目录")
            if not workspace_path:
                return
        else:
            workspace_path = self.project_manager.get_current_project_path()

        # 确认删除
        if messagebox.askyesno("确认删除", f"确定要删除项目吗？\n这将删除版本数据但不会删除工作文件。\n\n项目路径: {workspace_path}"):
            if self.project_manager.delete_project(workspace_path):
                messagebox.showinfo("成功", "项目删除成功")
                if self.project_manager.get_current_project_path() == workspace_path:
                    self._close_project()
            else:
                messagebox.showerror("错误", "项目删除失败")

    def _commit_version(self):
        """提交版本"""
        if not self.version_manager:
            return

        # 检查是否有变更
        if not self.current_changes:
            messagebox.showinfo("提示", "没有文件变更，无需提交版本")
            return

        # 输入版本描述（使用更大的输入框）
        description = self._show_version_description_dialog()
        if description is None:
            return

        if not description.strip():
            messagebox.showerror("错误", "版本描述不能为空")
            return

        try:
            # 创建版本
            version_number = self.version_manager.create_version(description.strip())
            if version_number:
                messagebox.showinfo("成功", f"版本 {version_number} 创建成功")
                self._refresh_data()
            else:
                messagebox.showerror("错误", "版本创建失败")
        except Exception as e:
            messagebox.showerror("错误", f"版本创建失败: {e}")

    def _rollback_version(self):
        """回滚版本"""
        if not self.version_manager:
            return

        # 获取选中的版本
        selected_items = self.versions_tree.selection()
        if not selected_items:
            messagebox.showinfo("提示", "请先选择要回滚的版本")
            return

        # 获取版本信息
        selected_item = selected_items[0]
        version_number = self.versions_tree.item(selected_item)['values'][0]
        version_id = None
        for version in self.all_versions:
            if version['version_number'] == version_number:
                version_id = version['id']
                break

        if version_id is None:
            messagebox.showerror("错误", "无法找到选中的版本")
            return

        # 确认回滚
        confirm_message = f"确定要回滚到版本 {version_number} 吗？\n\n这将恢复工作区到该版本的状态。"
        if messagebox.askyesno("确认回滚", confirm_message):
            # 询问是否备份当前状态（使用配置默认值）
            default_backup = config_manager.is_auto_backup_enabled()
            backup = messagebox.askyesno("备份", f"是否备份当前状态？\n(默认设置: {'是' if default_backup else '否'})")

            try:
                success = self.version_manager.rollback_to_version(version_id, backup)
                if success:
                    messagebox.showinfo("成功", f"已成功回滚到版本 {version_number}")
                    self._refresh_data()
                else:
                    messagebox.showerror("错误", "回滚失败")
            except Exception as e:
                messagebox.showerror("错误", f"回滚失败: {e}")

    def _export_version(self):
        """导出版本"""
        if not self.version_manager:
            return

        # 获取选中的版本
        selected_items = self.versions_tree.selection()
        if not selected_items:
            messagebox.showinfo("提示", "请先选择要导出的版本")
            return

        # 选择导出目录
        export_path = filedialog.askdirectory(title="选择导出目录")
        if not export_path:
            return

        # 获取版本信息
        selected_item = selected_items[0]
        version_number = self.versions_tree.item(selected_item)['values'][0]
        version_id = None
        for version in self.all_versions:
            if version['version_number'] == version_number:
                version_id = version['id']
                break

        if version_id is None:
            messagebox.showerror("错误", "无法找到选中的版本")
            return

        try:
            success = self.version_manager.export_version(version_id, export_path)
            if success:
                messagebox.showinfo("成功", f"版本 {version_number} 已导出到 {export_path}")
            else:
                messagebox.showerror("错误", "导出失败")
        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {e}")

    def _compare_versions(self):
        """比较版本"""
        if not self.version_manager:
            return

        if len(self.all_versions) < 2:
            messagebox.showinfo("提示", "需要至少两个版本才能进行比较")
            return

        try:
            dialog = VersionCompareDialog(self.root, self.version_manager, self.all_versions)
            dialog.show()
        except Exception as e:
            messagebox.showerror("错误", f"版本对比失败: {e}")

    def _on_version_double_click(self, event):
        """版本列表双击事件"""
        if not self.version_manager:
            return

        # 获取选中的版本
        selected_items = self.versions_tree.selection()
        if not selected_items:
            return

        # 获取版本信息
        selected_item = selected_items[0]
        version_number = self.versions_tree.item(selected_item)['values'][0]
        version_id = None
        for version in self.all_versions:
            if version['version_number'] == version_number:
                version_id = version['id']
                break

        if version_id is None:
            return

        try:
            # 获取版本详细信息
            version_details = self.version_manager.get_version_details(version_id)
            if version_details:
                dialog = VersionDetailsDialog(self.root, version_details)
                dialog.show()
        except Exception as e:
            messagebox.showerror("错误", f"获取版本详情失败: {e}")

    def _update_recent_projects_menu(self):
        """更新最近项目菜单"""
        # 清空现有菜单项
        self.recent_menu.delete(0, tk.END)

        recent_projects = config_manager.get_recent_projects()
        if recent_projects:
            for i, project_path in enumerate(recent_projects):
                # 只显示路径的最后一部分作为菜单项名称
                display_name = os.path.basename(project_path)
                if len(display_name) > 30:
                    display_name = display_name[:27] + "..."
                self.recent_menu.add_command(
                    label=f"{i+1}. {display_name}",
                    command=lambda p=project_path: self._open_project(p)
                )
        else:
            self.recent_menu.add_command(label="无最近项目", state=tk.DISABLED)

    def _show_version_description_dialog(self):
        """显示版本描述输入对话框"""
        from tkinter import simpledialog

        class VersionDescriptionDialog(simpledialog.Dialog):
            def body(self, master):
                """创建对话框主体"""
                ttk.Label(master, text="请输入版本描述:").grid(row=0, column=0, padx=5, pady=5)

                # 使用Text组件替代Entry，支持多行输入
                self.text_widget = tk.Text(master, height=6, width=40)
                self.text_widget.grid(row=1, column=0, padx=5, pady=5, sticky="ew")

                # 添加滚动条
                scrollbar = ttk.Scrollbar(master, orient=tk.VERTICAL, command=self.text_widget.yview)
                scrollbar.grid(row=1, column=1, sticky="ns")
                self.text_widget.configure(yscrollcommand=scrollbar.set)

                # 设置焦点
                self.text_widget.focus_set()

                return self.text_widget  # 初始焦点组件

            def apply(self):
                """获取用户输入"""
                self.result = self.text_widget.get(1.0, tk.END).strip()

        # 创建并显示对话框
        dialog = VersionDescriptionDialog(self.root, "版本描述")
        return dialog.result

    def _show_about(self):
        """显示关于对话框"""
        about_text = "本地文件版本管理工具\n\n"
        about_text += "一款轻量级的本地文件版本管理工具\n"
        about_text += "支持文件变更监控、版本记录和回滚\n\n"
        about_text += "版本: 1.0.0"
        messagebox.showinfo("关于", about_text)

    def run(self):
        """运行GUI应用"""
        try:
            self.root.mainloop()
        finally:
            self._cleanup()

    def _cleanup(self):
        """清理GUI资源"""
        try:
            if hasattr(self, 'root') and self.root.winfo_exists():
                # 清理Treeview组件
                if hasattr(self, 'changes_tree'):
                    for item in self.changes_tree.get_children():
                        self.changes_tree.delete(item)
                if hasattr(self, 'versions_tree'):
                    for item in self.versions_tree.get_children():
                        self.versions_tree.delete(item)

                # 关闭数据库连接
                if hasattr(self, 'project_manager'):
                    self.project_manager.close_project()

                # 销毁主窗口
                self.root.destroy()
        except Exception:
            # 忽略清理过程中的错误
            pass