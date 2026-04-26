"""
Dialog windows used by the VerMan GUI.
"""

import os
import platform
import subprocess
import tempfile
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Dict, List, Optional


class VersionCompareDialog:
    """Dialog for selecting and comparing two versions."""

    def __init__(
        self,
        parent,
        versions: List[Dict],
        compare_runner: Callable[[int, int, Callable[[Dict], None], Callable[[str], None]], None],
    ):
        self.parent = parent
        self.versions = versions
        self.compare_runner = compare_runner

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("版本对比")
        self.dialog.geometry("800x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.status_var = tk.StringVar(value="请选择两个版本进行比较")
        self._create_widgets()
        self._center_dialog()

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

        selection_frame = ttk.Frame(main_frame)
        selection_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(selection_frame, text="版本1:").pack(side=tk.LEFT, padx=(0, 5))
        self.version1_var = tk.StringVar()
        self.version1_combo = ttk.Combobox(selection_frame, textvariable=self.version1_var, state="readonly")
        self.version1_combo["values"] = [version["version_number"] for version in self.versions]
        self.version1_combo.pack(side=tk.LEFT, padx=(0, 20))

        ttk.Label(selection_frame, text="版本2:").pack(side=tk.LEFT, padx=(0, 5))
        self.version2_var = tk.StringVar()
        self.version2_combo = ttk.Combobox(selection_frame, textvariable=self.version2_var, state="readonly")
        self.version2_combo["values"] = [version["version_number"] for version in self.versions]
        self.version2_combo.pack(side=tk.LEFT)

        self.compare_button = ttk.Button(selection_frame, text="比较", command=self._compare_versions)
        self.compare_button.pack(side=tk.LEFT, padx=(20, 0))

        status_label = ttk.Label(main_frame, textvariable=self.status_var, anchor=tk.W)
        status_label.pack(fill=tk.X, pady=(0, 8))

        result_frame = ttk.LabelFrame(main_frame, text="比较结果")
        result_frame.pack(fill=tk.BOTH, expand=True)

        self.notebook = ttk.Notebook(result_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.only_v1_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.only_v1_frame, text="仅在版本1中")
        self.only_v1_tree = self._create_file_tree(self.only_v1_frame)

        self.only_v2_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.only_v2_frame, text="仅在版本2中")
        self.only_v2_tree = self._create_file_tree(self.only_v2_frame)

        self.different_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.different_frame, text="不同的文件")
        self.different_tree = self._create_file_tree(self.different_frame)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(button_frame, text="关闭", command=self.dialog.destroy).pack(side=tk.RIGHT)

        if len(self.versions) >= 2:
            self.version1_combo.current(0)
            self.version2_combo.current(1)
            self._compare_versions()

    def _create_file_tree(self, parent):
        tree = ttk.Treeview(parent, columns=("文件信息",), show="headings")
        tree.heading("文件信息", text="文件信息")
        tree.column("文件信息", width=750, anchor=tk.W)

        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        return tree

    def _compare_versions(self):
        version1_number = self.version1_var.get()
        version2_number = self.version2_var.get()
        if not version1_number or not version2_number:
            return
        if version1_number == version2_number:
            messagebox.showinfo("提示", "请选择不同的版本进行比较")
            return

        version1_id = None
        version2_id = None
        for version in self.versions:
            if version["version_number"] == version1_number:
                version1_id = version["id"]
            elif version["version_number"] == version2_number:
                version2_id = version["id"]

        if version1_id is None or version2_id is None:
            messagebox.showerror("错误", "无法找到选中的版本")
            return

        self.compare_button.config(state=tk.DISABLED)
        self.status_var.set("正在比较版本...")
        self.compare_runner(
            version1_id,
            version2_id,
            self._display_comparison_results,
            self._handle_compare_error,
        )

    def _handle_compare_error(self, error_message: str):
        self.compare_button.config(state=tk.NORMAL)
        self.status_var.set("版本比较失败")
        messagebox.showerror("错误", error_message)

    def _display_comparison_results(self, differences: Dict):
        for tree in (self.only_v1_tree, self.only_v2_tree, self.different_tree):
            for item in tree.get_children():
                tree.delete(item)

        for file_info in differences.get("only_in_first", []):
            self.only_v1_tree.insert("", tk.END, values=(self._format_file_entry(file_info),))

        for file_info in differences.get("only_in_second", []):
            self.only_v2_tree.insert("", tk.END, values=(self._format_file_entry(file_info),))

        for diff_info in differences.get("different", []):
            file_v1 = diff_info.get("file_in_v1", {})
            file_v2 = diff_info.get("file_in_v2", {})

            status_v1 = file_v1.get("file_status", "unknown")
            status_v2 = file_v2.get("file_status", "unknown")
            hash_v1 = file_v1.get("file_hash", "")[:8]
            hash_v2 = file_v2.get("file_hash", "")[:8]
            if status_v1 != status_v2:
                status_change = f"{status_v1}→{status_v2}"
            else:
                status_change = "内容变更"

            display_text = f"{diff_info['relative_path']} ({status_change}) [{hash_v1}→{hash_v2}]"
            self.different_tree.insert("", tk.END, values=(display_text,))

        different_count = len(differences.get("different", []))
        status_text = (
            f"比较完成：仅版本1 {len(differences.get('only_in_first', []))} 个，"
            f"仅版本2 {len(differences.get('only_in_second', []))} 个，"
            f"不同 {different_count} 个"
        )
        self.status_var.set(status_text)
        self.compare_button.config(state=tk.NORMAL)

    def _format_file_entry(self, file_info: Dict) -> str:
        status_map = {
            "add": "新增",
            "modify": "修改",
            "unmodified": "未变更",
            "delete": "删除",
        }
        status = status_map.get(file_info.get("file_status", ""), file_info.get("file_status", ""))
        file_hash = file_info.get("file_hash", "")
        hash_info = f" [{file_hash[:8]}]" if file_hash else ""
        return f"{status} - {file_info['relative_path']}{hash_info}"

    def show(self):
        try:
            self.dialog.wait_window()
        finally:
            self._cleanup()

    def _cleanup(self):
        try:
            if hasattr(self, "dialog") and self.dialog.winfo_exists():
                for tree_name in ("only_v1_tree", "only_v2_tree", "different_tree"):
                    tree = getattr(self, tree_name, None)
                    if tree is not None:
                        for item in tree.get_children():
                            tree.delete(item)
                self.dialog.destroy()
        except Exception:
            pass


class VersionDetailsDialog:
    """Dialog for displaying version metadata and opening historical files."""

    def __init__(self, parent, version_info: Dict, project_path: Optional[str] = None):
        self.parent = parent
        self.version_info = version_info
        self.project_path = project_path

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"版本详情 - {version_info['version_number']}")
        self.dialog.geometry("600x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()
        self._center_dialog()

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

        info_frame = ttk.LabelFrame(main_frame, text="版本信息")
        info_frame.pack(fill=tk.X, pady=(0, 10))

        info_grid = ttk.Frame(info_frame)
        info_grid.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(info_grid, text="版本号:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Label(info_grid, text=self.version_info["version_number"]).grid(row=0, column=1, sticky=tk.W)

        ttk.Label(info_grid, text="创建时间:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Label(info_grid, text=self.version_info["create_time"]).grid(row=1, column=1, sticky=tk.W)

        ttk.Label(info_grid, text="描述:").grid(row=2, column=0, sticky=tk.NW, padx=(0, 5))
        description = self.version_info.get("description", "无描述")
        ttk.Label(info_grid, text=description, wraplength=400).grid(row=2, column=1, sticky=tk.W)

        stats = self.version_info.get("statistics", {})
        ttk.Label(info_grid, text="新增文件:").grid(row=3, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Label(info_grid, text=str(stats.get("add_count", 0))).grid(row=3, column=1, sticky=tk.W)
        ttk.Label(info_grid, text="修改文件:").grid(row=4, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Label(info_grid, text=str(stats.get("modify_count", 0))).grid(row=4, column=1, sticky=tk.W)
        ttk.Label(info_grid, text="删除文件:").grid(row=5, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Label(info_grid, text=str(stats.get("delete_count", 0))).grid(row=5, column=1, sticky=tk.W)

        files_frame = ttk.LabelFrame(main_frame, text="文件列表")
        files_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("状态", "文件路径")
        self.files_tree = ttk.Treeview(files_frame, columns=columns, show="headings")
        self.files_tree.heading("状态", text="状态")
        self.files_tree.heading("文件路径", text="文件路径")
        self.files_tree.column("状态", width=80, anchor=tk.CENTER)
        self.files_tree.column("文件路径", width=450, anchor=tk.W)

        scrollbar = ttk.Scrollbar(files_frame, orient=tk.VERTICAL, command=self.files_tree.yview)
        self.files_tree.configure(yscrollcommand=scrollbar.set)

        self.files_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.files_tree.bind("<Double-Button-1>", self._on_file_double_click)
        self._fill_files_list()

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(button_frame, text="关闭", command=self.dialog.destroy).pack(side=tk.RIGHT)

    def _fill_files_list(self):
        status_map = {
            "add": "新增",
            "modify": "修改",
            "unmodified": "未变更",
            "delete": "删除",
        }
        for file_info in self.version_info.get("files", []):
            status = status_map.get(file_info["file_status"], file_info["file_status"])
            self.files_tree.insert("", tk.END, values=(status, file_info["relative_path"]))

    def _on_file_double_click(self, _event):
        selected_items = self.files_tree.selection()
        if not selected_items:
            return

        file_path = self.files_tree.item(selected_items[0])["values"][1]
        file_info = next(
            (file_info for file_info in self.version_info.get("files", []) if file_info["relative_path"] == file_path),
            None,
        )
        if not file_info:
            messagebox.showerror("错误", "无法找到文件信息")
            return
        if file_info["file_status"] == "delete":
            messagebox.showinfo("提示", "已删除的文件无法打开")
            return

        self._open_file_from_version(file_info)

    def _open_file_from_version(self, file_info: Dict):
        try:
            file_content = file_info.get("file_content")
            if file_content is None and file_info["file_status"] == "unmodified":
                if not self.project_path:
                    messagebox.showinfo("提示", "当前项目路径不可用，无法打开未变更文件")
                    return

                current_path = os.path.join(self.project_path, file_info["relative_path"])
                if not os.path.exists(current_path):
                    messagebox.showinfo("提示", "未变更文件在工作区中不存在，无法打开")
                    return

                with open(current_path, "rb") as file_handle:
                    file_content = file_handle.read()

            if file_content is None:
                messagebox.showerror("错误", "文件内容为空")
                return

            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=os.path.splitext(file_info["relative_path"])[1],
            ) as temp_file:
                if isinstance(file_content, bytes):
                    temp_file.write(file_content)
                else:
                    temp_file.write(file_content.encode("utf-8"))
                temp_file_path = temp_file.name

            self._open_with_system_default(temp_file_path)
        except Exception as exc:
            messagebox.showerror("错误", f"打开文件失败: {exc}")

    def _open_with_system_default(self, file_path: str):
        try:
            system = platform.system()
            if system == "Windows":
                os.startfile(file_path)
            elif system == "Darwin":
                subprocess.run(["open", file_path], check=False)
            elif system == "Linux":
                subprocess.run(["xdg-open", file_path], check=False)
            else:
                messagebox.showinfo("提示", f"不支持的操作系统: {system}")
        except Exception as exc:
            messagebox.showerror("错误", f"打开文件失败: {exc}")

    def show(self):
        try:
            self.dialog.wait_window()
        finally:
            self._cleanup()

    def _cleanup(self):
        try:
            if hasattr(self, "dialog") and self.dialog.winfo_exists():
                if hasattr(self, "files_tree"):
                    for item in self.files_tree.get_children():
                        self.files_tree.delete(item)
                self.dialog.destroy()
        except Exception:
            pass
