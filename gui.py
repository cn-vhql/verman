"""
图形用户界面模块
使用Tkinter实现简洁的版本管理界面
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import os
import sys
from typing import Optional, List
from project_manager import ProjectManager
from version_manager import VersionManager
from dialogs import VersionCompareDialog, VersionDetailsDialog
from config import config_manager
from logger import operation_logger
from license_manager import LicenseManager
from vip_dialog import VIPUpgradeDialog, VIPStatusDialog


class VersionManagerGUI:
    """版本管理工具GUI"""

    def __init__(self):
        """初始化GUI"""
        self.root = tk.Tk()
        self.root.title("VerMan - 版本管理工具")
        self.root.geometry("900x600")

        # 项目管理器
        self.project_manager = ProjectManager()
        self.version_manager: Optional[VersionManager] = None

        # 许可证管理器
        self.license_manager = LicenseManager()

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

        # VIP菜单
        vip_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="VIP", menu=vip_menu)

        # 更新VIP菜单标题和状态
        plan_type = self.license_manager.get_plan_type()
        print(f"[DEBUG] 创建VIP菜单 - Plan type: {plan_type}")
        print(f"[DEBUG] 创建VIP菜单 - Is VIP user: {self.license_manager.is_vip_user()}")

        if plan_type == 'vip':
            vip_menu.add_command(label=f"💎 VIP版 - {self.license_manager.get_license_info()['user_email']}", state=tk.DISABLED)
        else:
            vip_menu.add_command(label="🆓 免费版", state=tk.DISABLED)

        vip_menu.add_separator()
        vip_menu.add_command(label="查看VIP状态", command=self._show_vip_status)

        # 根据VIP状态决定升级菜单项是否可用
        if self.license_manager.is_vip_user():
            vip_menu.add_command(label="升级VIP", state=tk.DISABLED)
        else:
            vip_menu.add_command(label="升级VIP", command=self._upgrade_to_vip)

        # 设置菜单
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="设置", menu=settings_menu)
        settings_menu.add_command(label="配置设置", command=self._show_settings)
        settings_menu.add_separator()
        settings_menu.add_command(label="右键菜单管理", command=self._manage_context_menu)

        # 日志菜单
        log_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="日志", menu=log_menu)
        log_menu.add_command(label="查看操作日志", command=self._show_operation_logs)
        log_menu.add_separator()
        log_menu.add_command(label="清空日志", command=self._clear_logs)

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
        self.versions_tree.column('描述', width=300, anchor=tk.W)
        self.versions_tree.column('变更数', width=100, anchor=tk.CENTER)

        # 版本列表滚动条
        versions_scrollbar = ttk.Scrollbar(versions_frame, orient=tk.VERTICAL, command=self.versions_tree.yview)
        self.versions_tree.configure(yscrollcommand=versions_scrollbar.set)

        self.versions_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        versions_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 版本列表绑定双击事件
        self.versions_tree.bind('<Double-Button-1>', self._on_version_double_click)

        # 版本列表绑定右键菜单事件
        self.versions_tree.bind('<Button-3>', self._on_version_right_click)

        # 版本列表绑定选中变化事件
        self.versions_tree.bind('<<TreeviewSelect>>', self._on_version_select)

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
        # 获取当前工作目录作为默认路径
        current_dir = os.getcwd()
        workspace_path = filedialog.askdirectory(title="选择工作区目录", initialdir=current_dir)
        if not workspace_path:
            return

        # 创建项目
        if self.project_manager.create_project(workspace_path):
            messagebox.showinfo("成功", "项目创建成功")
            # 记录操作日志
            operation_logger.log_project_created(workspace_path)
            # 添加到最近项目
            config_manager.add_recent_project(workspace_path)
            self._update_recent_projects_menu()

            self.version_manager = VersionManager(
                self.project_manager.get_database_manager(),
                self.project_manager.get_file_manager(),
                config_manager
            )
            self._refresh_data()
        else:
            messagebox.showerror("错误", "项目创建失败，可能是目录不存在或已经是项目")
            operation_logger.log_error("创建项目", f"项目创建失败: {workspace_path}", workspace_path)

    def _open_project(self, workspace_path: str = None):
        """打开项目"""
        # 选择工作区目录
        if workspace_path is None:
            # 获取当前工作目录作为默认路径
            current_dir = os.getcwd()
            workspace_path = filedialog.askdirectory(title="选择项目目录", initialdir=current_dir)
        if not workspace_path:
            return

        # 打开项目
        if self.project_manager.open_project(workspace_path):
            # messagebox.showinfo("成功", "项目打开成功")
            # 记录操作日志
            operation_logger.log_project_opened(workspace_path)
            # 添加到最近项目
            config_manager.add_recent_project(workspace_path)
            self._update_recent_projects_menu()

            self.version_manager = VersionManager(
                self.project_manager.get_database_manager(),
                self.project_manager.get_file_manager(),
                config_manager
            )
            self._refresh_data()
        else:
            messagebox.showerror("错误", "项目打开失败，可能是目录不存在或不是有效的项目")
            operation_logger.log_error("打开项目", f"项目打开失败: {workspace_path}", workspace_path)

    def _close_project(self):
        """关闭项目"""
        if not self.project_manager.is_project_open():
            return

        if messagebox.askyesno("确认", "确定要关闭当前项目吗？"):
            project_path = self.project_manager.get_current_project_path()
            self.project_manager.close_project()
            self.version_manager = None
            self.current_changes = []
            self.all_versions = []

            # 记录操作日志
            if project_path:
                operation_logger.log_project_closed(project_path)

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
                # messagebox.showinfo("成功", f"版本 {version_number} 创建成功")
                # 记录操作日志
                project_path = self.project_manager.get_current_project_path()
                operation_logger.log_version_created(
                    version_number,
                    description.strip(),
                    len(self.current_changes),
                    project_path
                )
                self._refresh_data()
            else:
                messagebox.showerror("错误", "版本创建失败")
        except Exception as e:
            messagebox.showerror("错误", f"版本创建失败: {e}")
            project_path = self.project_manager.get_current_project_path()
            operation_logger.log_error("创建版本", str(e), project_path)

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
        try:
            result = messagebox.askyesno("确认回滚", confirm_message)
            if result:  # 只有用户点击"是"时才继续
                # 询问是否备份当前状态（使用配置默认值）
                default_backup = config_manager.is_auto_backup_enabled()
                backup_message = f"是否备份当前状态？\n(默认设置: {'是' if default_backup else '否'})"
                backup_result = messagebox.askyesno("备份", backup_message)

                try:
                    success = self.version_manager.rollback_to_version(version_id, backup_result)
                    if success:
                        messagebox.showinfo("成功", f"已成功回滚到版本 {version_number}")
                        # 记录操作日志
                        project_path = self.project_manager.get_current_project_path()
                        operation_logger.log_version_rollback(version_number, backup_result, project_path)
                        self._refresh_data()
                    else:
                        messagebox.showerror("错误", "回滚失败")
                except Exception as e:
                    messagebox.showerror("错误", f"回滚失败: {e}")
                    project_path = self.project_manager.get_current_project_path()
                    operation_logger.log_error("回滚版本", str(e), project_path)
        except Exception as e:
            # 处理可能的对话框异常（比如用户点击关闭按钮）
            pass

    def _export_version(self):
        """导出版本"""
        if not self.version_manager:
            return

        # 检查VIP权限
        if not self.license_manager.can_use_feature("can_export_version"):
            # 显示VIP升级对话框
            vip_dialog = VIPUpgradeDialog(self.root, "版本导出功能")
            result = vip_dialog.show()
            if result:  # 用户成功激活VIP
                self._handle_vip_activation_success("版本导出功能")
                # 重新执行功能
                self._execute_export_version()
            return

        self._execute_export_version()

    def _execute_export_version(self):
        """执行版本导出"""
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
                # 记录操作日志
                project_path = self.project_manager.get_current_project_path()
                operation_logger.log_version_exported(version_number, export_path, project_path)
            else:
                messagebox.showerror("错误", "导出失败")
        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {e}")
            project_path = self.project_manager.get_current_project_path()
            operation_logger.log_error("导出版本", str(e), project_path)

    def _compare_versions(self):
        """比较版本"""
        if not self.version_manager:
            return

        # 检查VIP权限
        if not self.license_manager.can_use_feature("can_compare_versions"):
            # 显示VIP升级对话框
            vip_dialog = VIPUpgradeDialog(self.root, "版本对比功能")
            result = vip_dialog.show()
            if result:  # 用户成功激活VIP
                self._handle_vip_activation_success("版本对比功能")
                # 重新执行功能
                self._execute_compare_versions()
            return

        self._execute_compare_versions()

    def _execute_compare_versions(self):
        """执行版本对比"""
        if len(self.all_versions) < 2:
            messagebox.showinfo("提示", "需要至少两个版本才能进行比较")
            return

        try:
            dialog = VersionCompareDialog(self.root, self.version_manager, self.all_versions)
            dialog.show()
        except Exception as e:
            messagebox.showerror("错误", f"版本对比失败: {e}")

    def _on_version_select(self, event):
        """版本列表选中变化事件"""
        # 当选中变化时，更新界面状态（特别是按钮状态）
        self._update_ui_state()

    def _on_version_double_click(self, event):
        """版本列表双击事件"""
        if not self.version_manager:
            return

        # 检查基础权限（查看版本详情）
        if not self.license_manager.can_use_feature("can_view_version_info"):
            messagebox.showerror("错误", "无法查看版本详情")
            return

        self._execute_version_details()

    def _execute_version_details(self):
        """执行版本详情查看"""
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
                dialog = VersionDetailsDialog(self.root, version_details, self.license_manager)
                dialog.show()
        except Exception as e:
            messagebox.showerror("错误", f"获取版本详情失败: {e}")

    def _on_version_right_click(self, event):
        """版本列表右键菜单事件"""
        if not self.version_manager:
            return

        # 获取点击位置的项目
        item = self.versions_tree.identify('item', event.x, event.y)
        if not item:
            return

        # 选中该项目
        self.versions_tree.selection_set(item)

        # 创建右键菜单
        context_menu = tk.Menu(self.root, tearoff=0)
        context_menu.add_command(label="查看详情", command=self._show_version_details)
        context_menu.add_separator()
        context_menu.add_command(label="导出版本", command=self._export_version)
        context_menu.add_command(label="回滚版本", command=self._rollback_version)

        # 显示右键菜单
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()

    def _show_version_details(self):
        """显示版本详情"""
        if not self.version_manager:
            return

        # 检查基础权限（查看版本信息）
        if not self.license_manager.can_use_feature("can_view_version_info"):
            messagebox.showerror("错误", "无法查看版本详情")
            return

        self._execute_version_details()

    def _update_recent_projects_menu(self):
        """更新最近项目菜单"""
        # 清空现有菜单项
        self.recent_menu.delete(0, tk.END)

        recent_projects = config_manager.get_recent_projects()
        if recent_projects:
            for i, project_path in enumerate(recent_projects):
                # 显示完整的项目路径
                if len(project_path) > 50:
                    # 如果路径太长，从后往前截断，保留开头的重要部分
                    display_name = "..." + project_path[-47:]
                else:
                    display_name = project_path
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
            def __init__(self, parent, title=None):
                """初始化对话框"""
                self.parent = parent
                super().__init__(parent, title)

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

            def _center_dialog(self):
                """将对话框居中显示在父窗口上"""
                self.update_idletasks()

                # 获取对话框的尺寸
                dialog_width = self.winfo_width()
                dialog_height = self.winfo_height()

                # 如果尺寸为0，使用默认值
                if dialog_width <= 1:
                    dialog_width = 400
                if dialog_height <= 1:
                    dialog_height = 200

                # 获取父窗口的位置和尺寸
                parent_x = self.parent.winfo_rootx()
                parent_y = self.parent.winfo_rooty()
                parent_width = self.parent.winfo_width()
                parent_height = self.parent.winfo_height()

                # 计算居中位置
                x = parent_x + (parent_width // 2) - (dialog_width // 2)
                y = parent_y + (parent_height // 2) - (dialog_height // 2)

                # 确保对话框不会超出屏幕边界
                screen_width = self.winfo_screenwidth()
                screen_height = self.winfo_screenheight()

                if x < 0:
                    x = 0
                if y < 0:
                    y = 0
                if x + dialog_width > screen_width:
                    x = screen_width - dialog_width
                if y + dialog_height > screen_height:
                    y = screen_height - dialog_height

                # 设置对话框位置
                self.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

            def show(self):
                """显示对话框并居中"""
                # 在对话框显示后立即居中
                self.after(100, self._center_dialog)
                self.wait_window()
                return self.result

        # 创建并显示对话框
        dialog = VersionDescriptionDialog(self.root, "版本描述")
        return dialog.result

    def _show_settings(self):
        """显示设置对话框"""
        dialog = SettingsDialog(self.root, config_manager)
        self.root.wait_window(dialog.dialog)
        # 设置对话框关闭后刷新相关状态
        # 需要刷新数据以应用新的忽略文件模式
        if self.project_manager.is_project_open():
            self._refresh_data()
        else:
            self._update_ui_state()

    def _manage_context_menu(self):
        """管理右键菜单"""
        dialog = ContextMenuManagerDialog(self.root)
        self.root.wait_window(dialog.dialog)

    def _show_about(self):
        """显示关于对话框"""
        # 获取VIP状态信息
        vip_status = "🆓 免费版" if not self.license_manager.is_vip_user() else "💎 VIP版"

        about_text = "VerMan - 版本管理工具\n\n"
        about_text += "VerMan是一款轻量级的本地文件版本管理工具\n"
        about_text += "支持文件变更监控、版本记录和回滚\n\n"
        about_text += f"版本: 1.0.0 | {vip_status}\n"

        if self.license_manager.is_vip_user():
            license_info = self.license_manager.get_license_info()
            about_text += f"VIP用户: {license_info.get('user_email', '')}\n"

        messagebox.showinfo("关于", about_text)

    def _show_vip_status(self):
        """显示VIP状态"""
        dialog = VIPStatusDialog(self.root)
        dialog.show()

    def _upgrade_to_vip(self):
        """升级到VIP"""
        vip_dialog = VIPUpgradeDialog(self.root, "所有高级功能")
        result = vip_dialog.show()

        if result:  # 用户成功激活VIP
            messagebox.showinfo("🎉 恭喜升级",
                             "恭喜您成功升级到VIP版！\n\n"
                             "现在您可以享受所有高级功能：\n"
                             "• 查看历史版本文件内容\n"
                             "• 版本对比功能\n"
                             "• 版本导出功能\n\n"
                             "感谢您的支持！")

            # 重新创建许可证管理器以更新权限状态
            self.license_manager = LicenseManager()
            # 更新VIP菜单
            self._update_vip_menu()

    def _update_vip_menu(self):
        """更新VIP菜单显示"""
        # 强制更新菜单 - 先清除现有菜单再重新创建
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        # 重新创建所有菜单
        self._create_menu()

    def _handle_vip_activation_success(self, feature_name: str = "所有高级功能"):
        """处理VIP激活成功后的更新"""
        messagebox.showinfo("感谢支持", f"VIP激活成功！现在可以使用{feature_name}了。")
        # 重新创建许可证管理器以更新权限状态
        self.license_manager = LicenseManager()

        # 调试信息
        print(f"[DEBUG] VIP激活成功后状态:")
        print(f"  Plan type: {self.license_manager.get_plan_type()}")
        print(f"  Is VIP user: {self.license_manager.is_vip_user()}")
        print(f"  Can view file content: {self.license_manager.can_use_feature('can_view_file_content')}")

        # 更新VIP菜单
        self._update_vip_menu()

    def _show_operation_logs(self):
        """显示操作日志对话框"""
        dialog = LogViewerDialog(self.root)
        self.root.wait_window(dialog.dialog)

    def _clear_logs(self):
        """清空日志"""
        if messagebox.askyesno("确认", "确定要清空所有操作日志吗？此操作无法撤销。"):
            try:
                operation_logger.clear_logs()
                messagebox.showinfo("成功", "日志已清空")
            except Exception as e:
                messagebox.showerror("错误", f"清空日志失败: {e}")

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


class SettingsDialog:
    """设置对话框"""

    def __init__(self, parent, config_manager):
        self.config_manager = config_manager
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("设置")
        self.dialog.geometry("550x500")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # 居中显示
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (550 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (500 // 2)
        self.dialog.geometry(f"550x500+{x}+{y}")

        self._create_widgets()
        self._load_settings()

    def _create_widgets(self):
        """创建界面组件"""
        # 主框架
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # 配置选项
        config_frame = ttk.LabelFrame(main_frame, text="配置选项")
        config_frame.pack(fill=tk.X, pady=(0, 20))

        # 自动备份
        self.auto_backup_var = tk.BooleanVar()
        auto_backup_check = ttk.Checkbutton(
            config_frame,
            text="回滚时自动备份当前状态",
            variable=self.auto_backup_var
        )
        auto_backup_check.pack(anchor=tk.W, padx=10, pady=5)

        # 最大版本数
        max_versions_frame = ttk.Frame(config_frame)
        max_versions_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(max_versions_frame, text="最大保留版本数:").pack(side=tk.LEFT)
        self.max_versions_var = tk.StringVar()
        max_versions_spin = ttk.Spinbox(
            max_versions_frame,
            from_=10,
            to=1000,
            textvariable=self.max_versions_var,
            width=10
        )
        max_versions_spin.pack(side=tk.LEFT, padx=(10, 5))
        ttk.Label(max_versions_frame, text="(0表示不限制)").pack(side=tk.LEFT)

        # 忽略文件模式
        ignore_frame = ttk.LabelFrame(main_frame, text="忽略文件模式")
        ignore_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

        ttk.Label(ignore_frame, text="每行一个文件模式 (支持 * 和 ? 通配符):").pack(anchor=tk.W, padx=10, pady=(10, 5))

        # 忽略文件列表
        list_frame = ttk.Frame(ignore_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.ignore_listbox = tk.Listbox(list_frame, height=8)
        ignore_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.ignore_listbox.yview)
        self.ignore_listbox.configure(yscrollcommand=ignore_scrollbar.set)

        self.ignore_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ignore_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 忽略文件编辑
        edit_frame = ttk.Frame(ignore_frame)
        edit_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.ignore_entry = ttk.Entry(edit_frame)
        self.ignore_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 设置小按钮样式
        small_button_style = {'padding': (8, 4)}

        ttk.Button(edit_frame, text="添加", command=self._add_ignore_pattern, width=8, **small_button_style).pack(side=tk.LEFT, padx=(5, 2))
        ttk.Button(edit_frame, text="删除", command=self._remove_ignore_pattern, width=8, **small_button_style).pack(side=tk.LEFT, padx=2)

        # 按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        # 设置按钮样式和高度
        button_style = {'padding': (10, 6)}

        ttk.Button(button_frame, text="确定", command=self._save_settings, **button_style).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="取消", command=self.dialog.destroy, **button_style).pack(side=tk.RIGHT)
        ttk.Button(button_frame, text="重置", command=self._reset_settings, **button_style).pack(side=tk.RIGHT, padx=(0, 5))

    def _load_settings(self):
        """加载设置"""
        # 加载自动备份设置
        self.auto_backup_var.set(self.config_manager.is_auto_backup_enabled())

        # 加载最大版本数
        max_versions = self.config_manager.get_max_versions_in_memory()
        self.max_versions_var.set(str(max_versions) if max_versions > 0 else "")

        # 加载忽略文件模式
        self.ignore_listbox.delete(0, tk.END)
        ignore_patterns = self.config_manager.get_ignore_patterns()
        for pattern in ignore_patterns:
            self.ignore_listbox.insert(tk.END, pattern)

    def _add_ignore_pattern(self):
        """添加忽略模式"""
        pattern = self.ignore_entry.get().strip()
        if pattern:
            self.ignore_listbox.insert(tk.END, pattern)
            self.ignore_entry.delete(0, tk.END)

    def _remove_ignore_pattern(self):
        """删除忽略模式"""
        selection = self.ignore_listbox.curselection()
        if selection:
            self.ignore_listbox.delete(selection[0])

    def _save_settings(self):
        """保存设置"""
        try:
            # 保存自动备份设置
            self.config_manager.set_auto_backup(self.auto_backup_var.get())

            # 保存最大版本数
            max_versions_str = self.max_versions_var.get().strip()
            max_versions = int(max_versions_str) if max_versions_str else 0
            self.config_manager.set_max_versions_in_memory(max_versions)

            # 保存忽略文件模式
            ignore_patterns = list(self.ignore_listbox.get(0, tk.END))
            self.config_manager.set_ignore_patterns(ignore_patterns)

            messagebox.showinfo("成功", "设置已保存")
            self.dialog.destroy()
        except Exception as e:
            messagebox.showerror("错误", f"保存设置失败: {e}")

    def _reset_settings(self):
        """重置设置"""
        if messagebox.askyesno("确认", "确定要重置所有设置到默认值吗？"):
            self.config_manager.reset_to_defaults()
            self._load_settings()
            messagebox.showinfo("成功", "设置已重置")


class ContextMenuManagerDialog:
    """右键菜单管理对话框"""

    def __init__(self, parent):
        self.parent = parent
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("右键菜单管理")
        self.dialog.geometry("450x350")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # 居中显示
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (450 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (350 // 2)
        self.dialog.geometry(f"450x350+{x}+{y}")

        self._create_widgets()
        self._check_context_menu_status()

    def _create_widgets(self):
        """创建界面组件"""
        # 主框架
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # 状态显示
        status_frame = ttk.LabelFrame(main_frame, text="当前状态")
        status_frame.pack(fill=tk.X, pady=(0, 20))

        self.status_label = ttk.Label(status_frame, text="正在检查右键菜单状态...")
        self.status_label.pack(anchor=tk.W, padx=10, pady=10)

        # 功能说明
        info_frame = ttk.LabelFrame(main_frame, text="功能说明")
        info_frame.pack(fill=tk.X, pady=(0, 20))

        info_text = """右键菜单功能可以让您在文件资源管理器中快速访问VerMan：

• 在文件夹上右键 → 直接打开该文件夹的版本管理
• 在文件夹空白处右键 → 打开当前文件夹的版本管理
• 在文件上右键 → 打开文件所在文件夹的版本管理

安装后将在Windows注册表中添加相应的右键菜单项。"""

        info_label = ttk.Label(info_frame, text=info_text, justify=tk.LEFT)
        info_label.pack(anchor=tk.W, padx=10, pady=10)

        # 操作按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        # 设置按钮样式和高度
        button_style = {'padding': (10, 6)}

        self.install_button = ttk.Button(button_frame, text="安装右键菜单", command=self._install_context_menu, **button_style)
        self.install_button.pack(side=tk.LEFT, padx=(0, 10))

        self.uninstall_button = ttk.Button(button_frame, text="卸载右键菜单", command=self._uninstall_context_menu, state=tk.DISABLED, **button_style)
        self.uninstall_button.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(button_frame, text="刷新状态", command=self._check_context_menu_status, **button_style).pack(side=tk.LEFT)

        # 关闭按钮
        ttk.Button(button_frame, text="关闭", command=self.dialog.destroy, **button_style).pack(side=tk.RIGHT)

    def _check_context_menu_status(self):
        """检查右键菜单状态"""
        try:
            if sys.platform != "win32":
                self.status_label.config(text="错误: 当前系统不支持右键菜单功能", foreground="red")
                return

            import winreg

            # 检查注册表项
            registry_keys = [
                r"Directory\Background\shell\VerMan",
                r"Directory\shell\VerMan",
                r"*\shell\VerMan"
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
                self.status_label.config(text=f"⚠ 右键菜单部分安装 ({installed_count}/3项)", foreground="orange")
                self.install_button.config(state=tk.NORMAL)
                self.uninstall_button.config(state=tk.NORMAL)
            else:
                self.status_label.config(text="✗ 右键菜单未安装", foreground="red")
                self.install_button.config(state=tk.NORMAL)
                self.uninstall_button.config(state=tk.DISABLED)

        except Exception as e:
            self.status_label.config(text=f"检查状态失败: {e}", foreground="red")

    def _install_context_menu(self):
        """安装右键菜单"""
        try:
            if sys.platform != "win32":
                messagebox.showerror("错误", "当前系统不支持右键菜单功能")
                return

            # 查找exe文件路径
            exe_path = self._find_exe_path()
            if not exe_path:
                messagebox.showerror("错误", "未找到VersionManager.exe文件\n请先运行 script/build_exe_simple.py 打包程序")
                return

            # 直接安装右键菜单
            success = self._install_context_menu_direct(exe_path)
            if success:
                messagebox.showinfo("成功", "右键菜单安装成功！\n\n现在可以在文件资源管理器中右键使用VerMan了。")
                self._check_context_menu_status()
            else:
                messagebox.showerror("失败", "右键菜单安装失败")

        except Exception as e:
            messagebox.showerror("错误", f"安装右键菜单失败: {e}")

    def _find_exe_path(self):
        """查找exe文件路径"""
        import os
        from pathlib import Path

        # 获取当前文件的目录（gui.py所在目录）
        current_dir = Path(__file__).parent.absolute()

        # 可能的exe文件位置
        possible_paths = [
            current_dir / "dist" / "VersionManager.exe",
            current_dir / "VersionManager.exe",
            current_dir / "build" / "exe.win-amd64-3.11" / "VersionManager.exe",
            current_dir / "build" / "exe.win32-3.11" / "VersionManager.exe",
        ]

        for path in possible_paths:
            if path.exists():
                return str(path)

        return None

    def _install_context_menu_direct(self, exe_path):
        """直接安装右键菜单"""
        try:
            import winreg

            # 创建目录背景右键菜单
            with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, r"Directory\\Background\\shell\\VerMan") as key:
                winreg.SetValueEx(key, None, 0, winreg.REG_SZ, "使用VerMan版本管理")
                with winreg.CreateKey(key, "command") as cmd_key:
                    winreg.SetValueEx(cmd_key, None, 0, winreg.REG_SZ, f'"{exe_path}" "%V"')

            # 创建文件夹右键菜单
            with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, r"Directory\\shell\\VerMan") as key:
                winreg.SetValueEx(key, None, 0, winreg.REG_SZ, "使用VerMan版本管理")
                with winreg.CreateKey(key, "command") as cmd_key:
                    winreg.SetValueEx(cmd_key, None, 0, winreg.REG_SZ, f'"{exe_path}" "%1"')

            # 创建文件右键菜单
            with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, r"*\\shell\\VerMan") as key:
                winreg.SetValueEx(key, None, 0, winreg.REG_SZ, "使用VerMan版本管理")
                with winreg.CreateKey(key, "command") as cmd_key:
                    winreg.SetValueEx(cmd_key, None, 0, winreg.REG_SZ, f'"{exe_path}" "%1"')

            return True

        except Exception as e:
            messagebox.showerror("错误", f"安装注册表项失败: {e}")
            return False

    def _uninstall_context_menu(self):
        """卸载右键菜单"""
        try:
            if sys.platform != "win32":
                messagebox.showerror("错误", "当前系统不支持右键菜单功能")
                return

            # 确认卸载
            if not messagebox.askyesno("确认", "确定要卸载右键菜单吗？\n卸载后将无法通过右键菜单快速访问VerMan。"):
                return

            # 直接卸载右键菜单
            success = self._uninstall_context_menu_direct()
            if success:
                messagebox.showinfo("成功", "右键菜单卸载成功！")
                self._check_context_menu_status()
            else:
                messagebox.showerror("失败", "右键菜单卸载失败")

        except Exception as e:
            messagebox.showerror("错误", f"卸载右键菜单失败: {e}")

    def _uninstall_context_menu_direct(self):
        """直接卸载右键菜单"""
        try:
            import winreg

            # 删除的注册表项
            registry_keys = [
                r"Directory\Background\shell\VerMan",
                r"Directory\shell\VerMan",
                r"*\shell\VerMan"
            ]

            success_count = 0
            for key_path in registry_keys:
                try:
                    # 先删除command子键
                    winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, key_path + r"\command")
                    # 再删除主键
                    winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, key_path)
                    success_count += 1
                except FileNotFoundError:
                    # 键不存在，跳过
                    pass
                except Exception as e:
                    # 其他错误，记录但继续处理其他键
                    print(f"删除注册表项失败 {key_path}: {e}")

            if success_count > 0 or True:  # 即使没有找到键也认为是成功的
                return True
            else:
                return False

        except Exception as e:
            messagebox.showerror("错误", f"删除注册表项失败: {e}")
            return False


class LogViewerDialog:
    """日志查看对话框"""

    def __init__(self, parent):
        """初始化日志查看对话框"""
        self.parent = parent
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("操作日志")
        self.dialog.geometry("800x500")
        self.dialog.resizable(True, True)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # 居中显示对话框
        self._center_dialog()

        self._create_widgets()
        self._load_logs()

    def _center_dialog(self):
        """将对话框居中显示在父窗口上"""
        self.dialog.update_idletasks()

        # 获取对话框的尺寸
        dialog_width = self.dialog.winfo_width()
        dialog_height = self.dialog.winfo_height()

        # 获取父窗口的位置和尺寸
        parent_x = self.parent.winfo_rootx()
        parent_y = self.parent.winfo_rooty()
        parent_width = self.parent.winfo_width()
        parent_height = self.parent.winfo_height()

        # 计算居中位置
        x = parent_x + (parent_width // 2) - (dialog_width // 2)
        y = parent_y + (parent_height // 2) - (dialog_height // 2)

        # 确保对话框不会超出屏幕边界
        screen_width = self.dialog.winfo_screenwidth()
        screen_height = self.dialog.winfo_screenheight()

        if x < 0:
            x = 0
        if y < 0:
            y = 0
        if x + dialog_width > screen_width:
            x = screen_width - dialog_width
        if y + dialog_height > screen_height:
            y = screen_height - dialog_height

        # 设置对话框位置
        self.dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

    def _create_widgets(self):
        """创建界面组件"""
        # 主框架
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 控制面板
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(0, 10))

        # 筛选控件
        ttk.Label(control_frame, text="筛选:").pack(side=tk.LEFT, padx=(0, 5))

        self.filter_var = tk.StringVar(value="全部")
        filter_combo = ttk.Combobox(control_frame, textvariable=self.filter_var,
                                   values=["全部", "INFO", "WARNING", "ERROR"],
                                   state="readonly", width=10)
        filter_combo.pack(side=tk.LEFT, padx=(0, 10))
        filter_combo.bind('<<ComboboxSelected>>', self._filter_logs)

        # 刷新按钮
        ttk.Button(control_frame, text="刷新", command=self._load_logs).pack(side=tk.LEFT, padx=(0, 5))

        # 清空按钮
        ttk.Button(control_frame, text="清空日志", command=self._clear_logs).pack(side=tk.LEFT, padx=(0, 5))

        # 日志数量显示
        self.count_label = ttk.Label(control_frame, text="共 0 条日志")
        self.count_label.pack(side=tk.RIGHT)

        # 日志列表
        log_frame = ttk.Frame(main_frame)
        log_frame.pack(fill=tk.BOTH, expand=True)

        # 创建Treeview
        columns = ('时间', '级别', '操作', '详情', '项目路径')
        self.log_tree = ttk.Treeview(log_frame, columns=columns, show='headings')

        # 设置列标题和宽度
        self.log_tree.heading('时间', text='时间')
        self.log_tree.heading('级别', text='级别')
        self.log_tree.heading('操作', text='操作')
        self.log_tree.heading('详情', text='详情')
        self.log_tree.heading('项目路径', text='项目路径')

        self.log_tree.column('时间', width=140, anchor=tk.CENTER)
        self.log_tree.column('级别', width=80, anchor=tk.CENTER)
        self.log_tree.column('操作', width=120, anchor=tk.W)
        self.log_tree.column('详情', width=300, anchor=tk.W)
        self.log_tree.column('项目路径', width=200, anchor=tk.W)

        # 滚动条
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_tree.yview)
        self.log_tree.configure(yscrollcommand=scrollbar.set)

        self.log_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(button_frame, text="关闭", command=self.dialog.destroy).pack(side=tk.RIGHT)

    def _load_logs(self):
        """加载日志"""
        try:
            # 获取所有日志
            all_logs = operation_logger.get_logs()
            self.all_logs = all_logs

            # 应用筛选
            self._filter_logs()
        except Exception as e:
            messagebox.showerror("错误", f"加载日志失败: {e}")

    def _filter_logs(self, event=None):
        """筛选日志"""
        try:
            # 清空现有内容
            for item in self.log_tree.get_children():
                self.log_tree.delete(item)

            # 获取筛选条件
            filter_level = self.filter_var.get()

            # 筛选日志
            if filter_level == "全部":
                filtered_logs = self.all_logs
            else:
                filtered_logs = [log for log in self.all_logs if log.get("level") == filter_level]

            # 添加到Treeview
            for log in reversed(filtered_logs):  # 最新的在前
                # 根据级别设置颜色标签
                tags = ()
                level = log.get("level", "INFO")
                if level == "ERROR":
                    tags = ("error",)
                elif level == "WARNING":
                    tags = ("warning",)

                self.log_tree.insert('', tk.END, values=(
                    log.get("timestamp", ""),
                    log.get("level", ""),
                    log.get("action", ""),
                    log.get("details", ""),
                    log.get("project_path", "")
                ), tags=tags)

            # 设置标签颜色
            self.log_tree.tag_configure("error", foreground="red")
            self.log_tree.tag_configure("warning", foreground="orange")

            # 更新计数
            self.count_label.config(text=f"共 {len(filtered_logs)} 条日志")

        except Exception as e:
            messagebox.showerror("错误", f"筛选日志失败: {e}")

    def _clear_logs(self):
        """清空日志"""
        if messagebox.askyesno("确认", "确定要清空所有操作日志吗？此操作无法撤销。"):
            try:
                operation_logger.clear_logs()
                self._load_logs()
                messagebox.showinfo("成功", "日志已清空")
            except Exception as e:
                messagebox.showerror("错误", f"清空日志失败: {e}")

    def show(self):
        """显示对话框"""
        try:
            self.dialog.wait_window()
        finally:
            self._cleanup()

    def _cleanup(self):
        """清理对话框资源"""
        try:
            if hasattr(self, 'dialog') and self.dialog.winfo_exists():
                # 清理Treeview组件
                if hasattr(self, 'log_tree'):
                    for item in self.log_tree.get_children():
                        self.log_tree.delete(item)
                # 销毁对话框
                self.dialog.destroy()
        except Exception:
            pass