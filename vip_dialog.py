"""
VIP升级对话框模块
提供VIP功能升级和激活码输入界面
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys
from license_manager import LicenseManager

# 尝试导入PIL，如果失败则使用占位符
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("Warning: PIL/Pillow not available, QR codes will show as text placeholders")


class VIPUpgradeDialog:
    """VIP升级对话框"""

    def __init__(self, parent, feature_name="高级功能"):
        """
        初始化VIP升级对话框

        Args:
            parent: 父窗口
            feature_name: 触发此对话框的功能名称
        """
        self.parent = parent
        self.feature_name = feature_name
        self.result = None
        self.license_manager = LicenseManager()

        # 创建对话框
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"升级VIP解锁{feature_name}")
        self.dialog.geometry("600x750")
        self.dialog.resizable(False, False)

        if parent:
            self.dialog.transient(parent)
            self.dialog.grab_set()

        self._create_widgets()
        self._center_dialog()
        # 延迟加载图片，确保对话框完全显示后再加载
        self.dialog.after(100, self._load_qr_codes)

    def _create_widgets(self):
        """创建界面组件"""
        # 主框架
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # 标题部分
        self._create_title_section(main_frame)

        # 价格部分
        self._create_pricing_section(main_frame)

        # 支付方式部分
        self._create_payment_section(main_frame)

        # 激活码输入部分
        self._create_activation_section(main_frame)

        # 按钮部分
        self._create_button_section(main_frame)

        # 状态标签 - 增强可见性
        self.status_label = ttk.Label(main_frame, text="", foreground="green",
                                    font=("Arial", 10, "bold"))
        self.status_label.pack(pady=(10, 0), fill=tk.X)

    def _create_title_section(self, parent):
        """创建标题部分"""
        title_frame = ttk.Frame(parent)
        title_frame.pack(fill=tk.X, pady=(0, 10))

        # VIP标题
        title_label = ttk.Label(title_frame, text="🔓 升级解锁VIP功能",
                               font=("Arial", 18, "bold"))
        title_label.pack()

    def _create_pricing_section(self, parent):
        """创建价格部分"""
        price_frame = ttk.LabelFrame(parent, text="💰 VIP版本价格", padding=8)
        price_frame.pack(fill=tk.X, pady=(0, 10))

        # 价格信息
        price_info = ttk.Frame(price_frame)
        price_info.pack(fill=tk.X)

        # VIP价格
        vip_price_frame = ttk.Frame(price_info)
        vip_price_frame.pack(fill=tk.X)

        ttk.Label(vip_price_frame, text="💎 VIP永久版",
                 font=("Arial", 13, "bold")).pack(side=tk.LEFT)

        ttk.Label(vip_price_frame, text="¥39.9",
                 font=("Arial", 15, "bold"), foreground="red").pack(side=tk.RIGHT)

    def _create_payment_section(self, parent):
        """创建支付方式部分"""
        payment_frame = ttk.LabelFrame(parent, text="💳 购买方式", padding=8)
        payment_frame.pack(fill=tk.X, pady=(0, 10))

        # 购买步骤
        steps_text = """📋 购买步骤：
1. 扫码支付 ¥39.9 → 截图 → 添加客服微信：qianglegend → 发送邮箱地址和付款截图获取激活码"""

        steps_label = ttk.Label(payment_frame, text=steps_text,
                               font=("Arial", 9), justify=tk.LEFT)
        steps_label.pack(anchor=tk.W, pady=(0, 8))

        # 收款码框架
        qr_codes_frame = ttk.Frame(payment_frame)
        qr_codes_frame.pack(fill=tk.X)

        # 支付宝收款码
        alipay_frame = ttk.Frame(qr_codes_frame)
        alipay_frame.pack(side=tk.LEFT, padx=(0, 15))

        ttk.Label(alipay_frame, text="支付宝",
                 font=("Arial", 10, "bold")).pack()

        self.alipay_label = tk.Label(alipay_frame, text="[加载中...]",
                                     relief=tk.RIDGE, width=100, height=100,
                                     bg="white", fg="gray")
        self.alipay_label.pack(pady=(3, 0))

        # 微信收款码
        wechat_frame = ttk.Frame(qr_codes_frame)
        wechat_frame.pack(side=tk.LEFT)

        ttk.Label(wechat_frame, text="微信",
                 font=("Arial", 10, "bold")).pack()

        self.wechat_label = tk.Label(wechat_frame, text="[加载中...]",
                                    relief=tk.RIDGE, width=100, height=100,
                                    bg="white", fg="gray")
        self.wechat_label.pack(pady=(3, 0))

    def _create_activation_section(self, parent):
        """创建激活码输入部分"""
        activation_frame = ttk.LabelFrame(parent, text="🔑 输入激活码", padding=8)
        activation_frame.pack(fill=tk.X, pady=(0, 10))

        # 邮箱输入
        ttk.Label(activation_frame, text="邮箱：").pack(anchor=tk.W)
        self.email_entry = ttk.Entry(activation_frame, font=("Arial", 11))
        self.email_entry.pack(fill=tk.X, pady=(3, 3))

        # 激活码输入
        ttk.Label(activation_frame, text="激活码：").pack(anchor=tk.W, pady=(10, 0))
        self.code_entry = ttk.Entry(activation_frame, font=("Courier", 11))
        self.code_entry.pack(fill=tk.X, pady=(3, 3))

        # 示例格式
        example_label = ttk.Label(activation_frame,
                                 text="格式：VMN-VIP-A4B8-C9D2E5F6",
                                 font=("Arial", 8), foreground="gray")
        example_label.pack(anchor=tk.W)

    def _create_button_section(self, parent):
        """创建按钮部分"""
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, pady=(0, 10))

        # 激活按钮
        ttk.Button(button_frame, text="🔓 激活VIP",
                  command=self._activate_vip,
                  style="Accent.TButton").pack(side=tk.RIGHT, padx=(5, 0))

        # 继续免费按钮
        ttk.Button(button_frame, text="🆓 继续免费使用",
                  command=self._continue_free).pack(side=tk.RIGHT)

    def _load_qr_codes(self):
        """加载收款码图片"""
        # 获取图片路径 - 支持开发环境和打包环境
        images_dir = self._get_images_directory()
        alipay_path = os.path.join(images_dir, 'alipay_qr.png')
        wechat_path = os.path.join(images_dir, 'wechat_qr.png')

        # 检查图片文件是否存在
        alipay_exists = os.path.exists(alipay_path)
        wechat_exists = os.path.exists(wechat_path)

        print(f"Images directory: {images_dir}")
        print(f"Alipay QR exists: {alipay_exists}")
        print(f"Wechat QR exists: {wechat_exists}")
        print(f"PIL available: {PIL_AVAILABLE}")

        # 加载支付宝收款码
        if alipay_exists and PIL_AVAILABLE:
            try:
                self._load_qr_image(self.alipay_label, alipay_path, "支付宝付款")
            except Exception as e:
                print(f"Failed to load alipay QR: {e}")
                self.alipay_label.config(text="支付宝收款\n请联系客服\nqianglegend")
        else:
            self.alipay_label.config(text="支付宝收款\n请联系客服\nqianglegend")

        # 加载微信收款码
        if wechat_exists and PIL_AVAILABLE:
            try:
                self._load_qr_image(self.wechat_label, wechat_path, "微信付款")
            except Exception as e:
                print(f"Failed to load wechat QR: {e}")
                self.wechat_label.config(text="微信收款\n请联系客服\nqianglegend")
        else:
            self.wechat_label.config(text="微信收款\n请联系客服\nqianglegend")

    def _get_images_directory(self):
        """获取图片目录路径，支持开发环境和打包环境"""
        # 首先尝试从当前目录下的images文件夹获取（开发环境）
        current_dir_images = os.path.join(os.path.dirname(__file__), 'images')
        if os.path.exists(current_dir_images):
            return current_dir_images

        # 尝试从工作目录下的images文件夹获取
        working_dir_images = os.path.join(os.getcwd(), 'images')
        if os.path.exists(working_dir_images):
            return working_dir_images

        # 尝试从打包后的资源路径获取（PyInstaller环境）
        if hasattr(sys, '_MEIPASS'):
            bundled_images = os.path.join(sys._MEIPASS, 'images')
            if os.path.exists(bundled_images):
                return bundled_images

        # 如果都找不到，返回当前目录下的images（即使不存在）
        return current_dir_images

    def _load_qr_image(self, label_widget, image_path, alt_text):
        """加载二维码图片"""
        # 加载并调整图片大小
        image = Image.open(image_path)
        # 调整图片大小以适应标签 - 增大尺寸到250x250
        image = image.resize((250, 250), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(image)

        # 显示图片 - 调整标签尺寸以适应更大的图片
        label_widget.config(image=photo, text="", width=250, height=250)
        label_widget.image = photo  # 保持引用防止垃圾回收
        print(f"Successfully loaded {alt_text} from {image_path}")

    def _activate_vip(self):
        """激活VIP功能"""
        activation_code = self.code_entry.get().strip().upper()
        user_email = self.email_entry.get().strip()

        # 验证输入
        if not activation_code:
            messagebox.showerror("错误", "请输入激活码")
            return

        if not user_email:
            messagebox.showerror("错误", "请输入邮箱")
            return

        try:
            success, message = self.license_manager.activate_vip_license(activation_code, user_email)

            if success:
                self.status_label.config(text=message, foreground="green")
                self.result = True

                # 显示成功消息
                messagebox.showinfo("🎉 激活成功",
                                   f"{message}\n\n"
                                   f"现在您可以使用所有VIP功能了！\n"
                                   f"感谢您的支持！")

                # 延迟关闭对话框
                self.dialog.after(2000, self.dialog.destroy)
            else:
                messagebox.showerror("激活失败", message)

        except Exception as e:
            messagebox.showerror("激活失败", f"激活失败：{str(e)}")

    def _continue_free(self):
        """继续免费使用"""
        self.result = False
        self.dialog.destroy()

    def _center_dialog(self):
        """居中显示对话框"""
        self.dialog.update_idletasks()

        # 获取屏幕尺寸
        screen_width = self.dialog.winfo_screenwidth()
        screen_height = self.dialog.winfo_screenheight()

        # 计算居中位置
        x = (screen_width - 600) // 2
        y = (screen_height - 750) // 2

        # 确保不超出屏幕边界
        x = max(0, x)
        y = max(0, y)

        self.dialog.geometry(f"600x750+{x}+{y}")

    def show(self) -> bool:
        """显示对话框并等待结果

        Returns:
            用户是否成功激活VIP
        """
        try:
            self.dialog.wait_window()
        except:
            pass
        finally:
            try:
                self.dialog.destroy()
            except:
                pass

        return self.result or False


class VIPStatusDialog:
    """VIP状态查看对话框"""

    def __init__(self, parent):
        """初始化VIP状态对话框"""
        self.parent = parent
        self.license_manager = LicenseManager()

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("VIP状态信息")
        self.dialog.geometry("600x700")
        self.dialog.resizable(False, False)

        if parent:
            self.dialog.transient(parent)
            self.dialog.grab_set()

        self._create_widgets()
        self._center_dialog()

    def _create_widgets(self):
        """创建界面组件"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # 获取许可证信息
        license_info = self.license_manager.check_activation_status()

        # 标题
        if license_info['is_activated']:
            title = "🎉 VIP用户状态"
            title_color = "green"
        else:
            title = "🆓 免费版用户"
            title_color = "blue"

        title_label = ttk.Label(main_frame, text=title,
                                font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))

        # 状态信息
        status_frame = ttk.LabelFrame(main_frame, text="当前状态", padding=10)
        status_frame.pack(fill=tk.X, pady=(0, 20))

        # 显示状态信息
        self._display_status_info(status_frame, license_info)

        # 功能列表
        features_frame = ttk.LabelFrame(main_frame, text="可用功能", padding=10)
        features_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

        self._display_features(features_frame, license_info['features'])

        # 按钮
        if not license_info['is_activated']:
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X)

            ttk.Button(button_frame, text="🔓 升级VIP",
                      command=self._upgrade_vip).pack(side=tk.RIGHT)

        ttk.Button(main_frame, text="关闭", command=self.dialog.destroy).pack(pady=(10, 0))

    def _display_status_info(self, parent, license_info):
        """显示状态信息"""
        info_items = [
            ("版本类型", "💎 VIP版" if license_info['is_activated'] else "🆓 免费版"),
            ("激活状态", "✅ 已激活" if license_info['is_activated'] else "❌ 未激活"),
        ]

        if license_info['is_activated']:
            info_items.extend([
                ("用户邮箱", license_info['user_email']),
                ("激活时间", license_info['activated_at'][:19].replace('T', ' ')),
                ("设备ID", license_info['machine_id'])
            ])

        for label, value in info_items:
            frame = ttk.Frame(parent)
            frame.pack(fill=tk.X, pady=2)

            ttk.Label(frame, text=f"{label}：").pack(side=tk.LEFT)
            ttk.Label(frame, text=value, font=("Arial", 10, "bold")).pack(side=tk.LEFT)

    def _display_features(self, parent, features):
        """显示功能列表"""
        # 基础功能（免费版都有）
        basic_features = [
            ("项目管理", "✅"),
            ("版本提交", "✅"),
            ("版本回滚", "✅"),
            ("忽略文件配置", "✅"),
            ("查看版本基本信息", "✅" if features.get('can_view_version_info') else "❌"),
        ]

        # VIP高级功能
        vip_features = [
            ("🔒 打开历史文件内容", "✅" if features.get('can_open_file_content') else "❌"),
            ("🔒 版本对比功能", "✅" if features.get('can_compare_versions') else "❌"),
            ("🔒 版本导出功能", "✅" if features.get('can_export_version') else "❌"),
            ("🔒 批量文件操作", "✅" if features.get('can_open_file_content') else "❌"),
            ("🔒 高级搜索和过滤", "✅" if features.get('can_compare_versions') else "❌"),
            ("🔒 优先技术支持", "✅" if features.get('can_export_version') else "❌"),
        ]

        # 显示基础功能
        basic_label = ttk.Label(parent, text="📋 基础功能", font=("Arial", 10, "bold"))
        basic_label.pack(anchor=tk.W, pady=(0, 5))

        for feature, status in basic_features:
            frame = ttk.Frame(parent)
            frame.pack(fill=tk.X, pady=2)

            ttk.Label(frame, text=status).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Label(frame, text=feature).pack(side=tk.LEFT)

        # 分隔线
        separator_frame = ttk.Frame(parent)
        separator_frame.pack(fill=tk.X, pady=10)

        separator_line = ttk.Separator(separator_frame, orient='horizontal')
        separator_line.pack(fill=tk.X)

        # 显示VIP功能
        vip_label = ttk.Label(parent, text="💎 VIP高级功能", font=("Arial", 10, "bold"))
        vip_label.pack(anchor=tk.W, pady=(0, 5))

        for feature, status in vip_features:
            frame = ttk.Frame(parent)
            frame.pack(fill=tk.X, pady=2)

            ttk.Label(frame, text=status).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Label(frame, text=feature).pack(side=tk.LEFT)

    def _upgrade_vip(self):
        """升级VIP"""
        self.dialog.destroy()
        vip_dialog = VIPUpgradeDialog(self.parent, "所有高级功能")
        vip_dialog.show()

    def _center_dialog(self):
        """居中显示对话框"""
        self.dialog.update_idletasks()

        screen_width = self.dialog.winfo_screenwidth()
        screen_height = self.dialog.winfo_screenheight()

        x = (screen_width - 600) // 2
        y = (screen_height - 700) // 2

        x = max(0, x)
        y = max(0, y)

        self.dialog.geometry(f"600x700+{x}+{y}")

    def show(self):
        """显示对话框"""
        try:
            self.dialog.wait_window()
        except:
            pass
        finally:
            try:
                self.dialog.destroy()
            except:
                pass