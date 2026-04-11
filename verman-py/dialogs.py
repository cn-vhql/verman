"""
对话框模块
包含各种自定义对话框
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Dict, Optional
import os
import tempfile
import subprocess
import platform


class VersionCompareDialog:
    """版本对比对话框"""

    def __init__(self, parent, version_manager, versions: List[Dict]):
        """
        初始化版本对比对话框

        Args:
            parent: 父窗口
            version_manager: 版本管理器
            versions: 版本列表
        """
        self.parent = parent
        self.version_manager = version_manager
        self.versions = versions
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("版本对比")
        self.dialog.geometry("800x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # 居中显示对话框
        self._center_dialog()

        self._create_widgets()

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

        # 版本选择框架
        selection_frame = ttk.Frame(main_frame)
        selection_frame.pack(fill=tk.X, pady=(0, 10))

        # 版本1选择
        ttk.Label(selection_frame, text="版本1:").pack(side=tk.LEFT, padx=(0, 5))
        self.version1_var = tk.StringVar()
        self.version1_combo = ttk.Combobox(selection_frame, textvariable=self.version1_var, state="readonly")
        self.version1_combo['values'] = [v['version_number'] for v in self.versions]
        self.version1_combo.pack(side=tk.LEFT, padx=(0, 20))
        self.version1_combo.bind('<<ComboboxSelected>>', self._on_version_selected)

        # 版本2选择
        ttk.Label(selection_frame, text="版本2:").pack(side=tk.LEFT, padx=(0, 5))
        self.version2_var = tk.StringVar()
        self.version2_combo = ttk.Combobox(selection_frame, textvariable=self.version2_var, state="readonly")
        self.version2_combo['values'] = [v['version_number'] for v in self.versions]
        self.version2_combo.pack(side=tk.LEFT)
        self.version2_combo.bind('<<ComboboxSelected>>', self._on_version_selected)

        # 比较按钮
        ttk.Button(selection_frame, text="比较", command=self._compare_versions).pack(side=tk.LEFT, padx=(20, 0))

        # 结果框架
        result_frame = ttk.LabelFrame(main_frame, text="比较结果")
        result_frame.pack(fill=tk.BOTH, expand=True)

        # 创建Notebook来组织不同类型的差异
        self.notebook = ttk.Notebook(result_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 仅在版本1中的文件
        self.only_v1_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.only_v1_frame, text="仅在版本1中")
        self.only_v1_tree = self._create_file_tree(self.only_v1_frame)

        # 仅在版本2中的文件
        self.only_v2_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.only_v2_frame, text="仅在版本2中")
        self.only_v2_tree = self._create_file_tree(self.only_v2_frame)

        # 不同的文件
        self.different_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.different_frame, text="不同的文件")
        self.different_tree = self._create_file_tree(self.different_frame)

        # 按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(button_frame, text="关闭", command=self.dialog.destroy).pack(side=tk.RIGHT)

        # 默认选择前两个版本
        if len(self.versions) >= 2:
            self.version1_combo.current(0)
            self.version2_combo.current(1)
            self._compare_versions()

    def _create_file_tree(self, parent):
        """创建文件列表树"""
        tree = ttk.Treeview(parent, columns=('文件信息',), show='headings')
        tree.heading('文件信息', text='文件信息')
        tree.column('文件信息', width=750, anchor=tk.W)

        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        return tree

    def _on_version_selected(self, event):
        """版本选择事件"""
        if self.version1_var.get() and self.version2_var.get():
            self._compare_versions()

    def _compare_versions(self):
        """比较版本"""
        version1_number = self.version1_var.get()
        version2_number = self.version2_var.get()

        if not version1_number or not version2_number:
            return

        if version1_number == version2_number:
            messagebox.showinfo("提示", "请选择不同的版本进行比较")
            return

        # 获取版本ID
        version1_id = None
        version2_id = None
        for version in self.versions:
            if version['version_number'] == version1_number:
                version1_id = version['id']
            elif version['version_number'] == version2_number:
                version2_id = version['id']

        if version1_id is None or version2_id is None:
            messagebox.showerror("错误", "无法找到选中的版本")
            return

        try:
            # 执行比较
            differences = self.version_manager.compare_versions(version1_id, version2_id)
            self._display_comparison_results(differences)
        except Exception as e:
            messagebox.showerror("错误", f"版本比较失败: {e}")

    def _display_comparison_results(self, differences: Dict):
        """显示比较结果"""
        # 清空现有结果
        for item in self.only_v1_tree.get_children():
            self.only_v1_tree.delete(item)
        for item in self.only_v2_tree.get_children():
            self.only_v2_tree.delete(item)
        for item in self.different_tree.get_children():
            self.different_tree.delete(item)

        # 显示仅在版本1中的文件
        for file_info in differences.get('only_in_first', []):
            status = file_info['file_status'].upper()
            if status == 'ADD':
                status = '新增'
            elif status == 'MODIFY':
                status = '修改'
            elif status == 'UNMODIFIED':
                status = '未变更'
            elif status == 'DELETE':
                status = '删除'

            # 添加哈希值信息（用于调试）
            file_hash = file_info.get('file_hash', '')
            hash_info = f" [{file_hash[:8]}]" if file_hash else ""

            display_text = f"{status} - {file_info['relative_path']}{hash_info}"
            self.only_v1_tree.insert('', tk.END, values=(display_text,))

        # 显示仅在版本2中的文件
        for file_info in differences.get('only_in_second', []):
            status = file_info['file_status'].upper()
            if status == 'ADD':
                status = '新增'
            elif status == 'MODIFY':
                status = '修改'
            elif status == 'UNMODIFIED':
                status = '未变更'
            elif status == 'DELETE':
                status = '删除'

            # 添加哈希值信息（用于调试）
            file_hash = file_info.get('file_hash', '')
            hash_info = f" [{file_hash[:8]}]" if file_hash else ""

            display_text = f"{status} - {file_info['relative_path']}{hash_info}"
            self.only_v2_tree.insert('', tk.END, values=(display_text,))

        # 显示不同的文件（内容或状态变化）
        for diff_info in differences.get('different', []):
            file_v1 = diff_info.get('file_in_v1', {})
            file_v2 = diff_info.get('file_in_v2', {})

            # 构建状态变化描述
            status_v1 = file_v1.get('file_status', 'unknown')
            status_v2 = file_v2.get('file_status', 'unknown')

            hash_v1 = file_v1.get('file_hash', '')[:8] if file_v1.get('file_hash') else ''
            hash_v2 = file_v2.get('file_hash', '')[:8] if file_v2.get('file_hash') else ''

            # 状态变化描述
            if status_v1 != status_v2:
                status_change = f"{status_v1}→{status_v2}"
            else:
                status_change = "内容变更"

            display_text = f"{diff_info['relative_path']} ({status_change}) [{hash_v1}→{hash_v2}]"
            self.different_tree.insert('', tk.END, values=(display_text,))

    def show(self):
        """显示对话框并等待结果"""
        try:
            self.dialog.wait_window()
        finally:
            self._cleanup()
        return self.result

    def _cleanup(self):
        """清理对话框资源"""
        try:
            if hasattr(self, 'dialog') and self.dialog.winfo_exists():
                # 清理Treeview组件
                if hasattr(self, 'only_v1_tree'):
                    for item in self.only_v1_tree.get_children():
                        self.only_v1_tree.delete(item)
                if hasattr(self, 'only_v2_tree'):
                    for item in self.only_v2_tree.get_children():
                        self.only_v2_tree.delete(item)
                if hasattr(self, 'different_tree'):
                    for item in self.different_tree.get_children():
                        self.different_tree.delete(item)

                # 销毁对话框
                self.dialog.destroy()
        except Exception:
            # 忽略清理过程中的错误
            pass


class VersionDetailsDialog:
    """版本详情对话框"""

    def __init__(self, parent, version_info: Dict, license_manager=None):
        """
        初始化版本详情对话框

        Args:
            parent: 父窗口
            version_info: 版本信息
            license_manager: 许可证管理器（用于VIP权限检查）
        """
        self.parent = parent
        self.version_info = version_info
        self.license_manager = license_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"版本详情 - {version_info['version_number']}")
        self.dialog.geometry("600x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # 居中显示对话框
        self._center_dialog()

        self._create_widgets()

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

        # 版本信息框架
        info_frame = ttk.LabelFrame(main_frame, text="版本信息")
        info_frame.pack(fill=tk.X, pady=(0, 10))

        # 版本基本信息
        info_grid = ttk.Frame(info_frame)
        info_grid.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(info_grid, text="版本号:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Label(info_grid, text=self.version_info['version_number']).grid(row=0, column=1, sticky=tk.W)

        ttk.Label(info_grid, text="创建时间:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Label(info_grid, text=self.version_info['create_time']).grid(row=1, column=1, sticky=tk.W)

        ttk.Label(info_grid, text="描述:").grid(row=2, column=0, sticky=tk.NW, padx=(0, 5))
        description = self.version_info.get('description', '无描述')
        ttk.Label(info_grid, text=description, wraplength=400).grid(row=2, column=1, sticky=tk.W)

        # 变更统计
        stats = self.version_info.get('statistics', {})
        ttk.Label(info_grid, text="新增文件:").grid(row=3, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Label(info_grid, text=str(stats.get('add_count', 0))).grid(row=3, column=1, sticky=tk.W)

        ttk.Label(info_grid, text="修改文件:").grid(row=4, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Label(info_grid, text=str(stats.get('modify_count', 0))).grid(row=4, column=1, sticky=tk.W)

        ttk.Label(info_grid, text="删除文件:").grid(row=5, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Label(info_grid, text=str(stats.get('delete_count', 0))).grid(row=5, column=1, sticky=tk.W)

        # 文件列表框架
        files_frame = ttk.LabelFrame(main_frame, text="文件列表")
        files_frame.pack(fill=tk.BOTH, expand=True)

        # 文件列表树
        columns = ('状态', '文件路径')
        self.files_tree = ttk.Treeview(files_frame, columns=columns, show='headings')
        self.files_tree.heading('状态', text='状态')
        self.files_tree.heading('文件路径', text='文件路径')
        self.files_tree.column('状态', width=80, anchor=tk.CENTER)
        self.files_tree.column('文件路径', width=450, anchor=tk.W)

        # 滚动条
        scrollbar = ttk.Scrollbar(files_frame, orient=tk.VERTICAL, command=self.files_tree.yview)
        self.files_tree.configure(yscrollcommand=scrollbar.set)

        self.files_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 绑定双击事件
        self.files_tree.bind('<Double-Button-1>', self._on_file_double_click)

        # 填充文件列表
        self._fill_files_list()

        # 按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(button_frame, text="关闭", command=self.dialog.destroy).pack(side=tk.RIGHT)

    def _fill_files_list(self):
        """填充文件列表"""
        files = self.version_info.get('files', [])
        for file_info in files:
            status = file_info['file_status'].upper()
            if status == 'ADD':
                status = '新增'
            elif status == 'MODIFY':
                status = '修改'
            elif status == 'UNMODIFIED':
                status = '未变更'
            elif status == 'DELETE':
                status = '删除'

            self.files_tree.insert('', tk.END, values=(status, file_info['relative_path']))

    def _on_file_double_click(self, event):
        """文件列表双击事件"""
        # 检查VIP权限（打开文件内容是VIP功能）
        if self.license_manager and not self.license_manager.can_use_feature('can_open_file_content'):
            # 导入VIP对话框（避免循环导入）
            try:
                from vip_dialog import VIPUpgradeDialog
                vip_dialog = VIPUpgradeDialog(self.parent, "打开历史文件内容")
                vip_dialog.show()
            except ImportError:
                messagebox.showinfo("提示", "打开历史文件内容需要升级VIP版本")
            return

        # 获取选中的文件
        selected_items = self.files_tree.selection()
        if not selected_items:
            return

        selected_item = selected_items[0]
        file_path = self.files_tree.item(selected_item)['values'][1]

        # 获取文件信息
        files = self.version_info.get('files', [])
        file_info = None
        for file in files:
            if file['relative_path'] == file_path:
                file_info = file
                break

        if not file_info:
            messagebox.showerror("错误", "无法找到文件信息")
            return

        # 检查文件状态
        if file_info['file_status'] == 'DELETE':
            messagebox.showinfo("提示", "已删除的文件无法打开")
            return

        # 尝试打开文件
        self._open_file_from_version(file_info)

    def _open_file_from_version(self, file_info):
        """从版本中打开文件"""
        try:
            # 获取文件内容
            file_content = file_info.get('file_content')

            # 如果文件内容为空且是未变更文件，尝试从工作区读取
            if not file_content and file_info['file_status'] == 'unmodified':
                try:
                    # 尝试从当前工作区读取文件
                    current_path = os.path.join(os.getcwd(), file_info['relative_path'])
                    if os.path.exists(current_path):
                        with open(current_path, 'rb') as f:
                            file_content = f.read()
                    else:
                        messagebox.showinfo("提示", "未变更文件在工作区中不存在，无法打开")
                        return
                except Exception as e:
                    messagebox.showinfo("提示", f"无法读取未变更文件: {e}")
                    return

            if not file_content:
                messagebox.showerror("错误", "文件内容为空")
                return

            # 创建临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_info['relative_path'])[1]) as temp_file:
                # 如果是二进制内容，直接写入；如果是文本内容，确保正确编码
                if isinstance(file_content, bytes):
                    temp_file.write(file_content)
                else:
                    temp_file.write(file_content.encode('utf-8'))
                temp_file_path = temp_file.name

            # 使用系统默认程序打开文件
            self._open_with_system_default(temp_file_path)

        except Exception as e:
            messagebox.showerror("错误", f"打开文件失败: {e}")

    def _open_with_system_default(self, file_path):
        """使用系统默认程序打开文件"""
        try:
            system = platform.system()

            if system == 'Windows':
                # Windows系统
                os.startfile(file_path)
            elif system == 'Darwin':
                # macOS系统
                subprocess.run(['open', file_path])
            elif system == 'Linux':
                # Linux系统
                subprocess.run(['xdg-open', file_path])
            else:
                messagebox.showinfo("提示", f"不支持的操作系统: {system}")
                return

        except Exception as e:
            messagebox.showerror("错误", f"打开文件失败: {e}")

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
                if hasattr(self, 'files_tree'):
                    for item in self.files_tree.get_children():
                        self.files_tree.delete(item)

                # 销毁对话框
                self.dialog.destroy()
        except Exception:
            # 忽略清理过程中的错误
            pass