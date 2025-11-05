"""
对话框模块
包含各种自定义对话框
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Dict, Optional


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

        self._create_widgets()

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
        tree = ttk.Treeview(parent, columns=('文件路径',), show='headings')
        tree.heading('文件路径', text='文件路径')
        tree.column('文件路径', width=700, anchor=tk.W)

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
            elif status == 'DELETE':
                status = '删除'
            self.only_v1_tree.insert('', tk.END, values=(f"{status} - {file_info['relative_path']}",))

        # 显示仅在版本2中的文件
        for file_info in differences.get('only_in_second', []):
            status = file_info['file_status'].upper()
            if status == 'ADD':
                status = '新增'
            elif status == 'MODIFY':
                status = '修改'
            elif status == 'DELETE':
                status = '删除'
            self.only_v2_tree.insert('', tk.END, values=(f"{status} - {file_info['relative_path']}",))

        # 显示不同的文件
        for diff_info in differences.get('different', []):
            self.different_tree.insert('', tk.END, values=(diff_info['relative_path'],))

    def show(self):
        """显示对话框并等待结果"""
        self.dialog.wait_window()
        return self.result


class VersionDetailsDialog:
    """版本详情对话框"""

    def __init__(self, parent, version_info: Dict):
        """
        初始化版本详情对话框

        Args:
            parent: 父窗口
            version_info: 版本信息
        """
        self.parent = parent
        self.version_info = version_info

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"版本详情 - {version_info['version_number']}")
        self.dialog.geometry("600x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

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
            elif status == 'DELETE':
                status = '删除'

            self.files_tree.insert('', tk.END, values=(status, file_info['relative_path']))

    def show(self):
        """显示对话框"""
        self.dialog.wait_window()