"""
许可证管理模块
负责VIP功能的权限管理和激活码验证
"""

import os
import json
import hashlib
import hmac
import platform
import uuid
import tkinter as tk
from tkinter import messagebox
from datetime import datetime
from typing import Dict, Any, Optional, Tuple


class LicenseManager:
    """许可证管理器，负责VIP功能权限控制"""

    def __init__(self):
        """初始化许可证管理器"""
        self.license_file = os.path.expanduser("~/.verman_license.json")
        self.secret_key = "verman_vip_secret_key_2024"  # 密钥，请妥善保管
        self.machine_id = self._generate_machine_id()
        self.feature_flags = self._load_feature_flags()

    def _generate_machine_id(self) -> str:
        """生成机器唯一标识符"""
        try:
            # 收集硬件信息
            machine_info = {
                'system_uuid': str(uuid.getnode()),
                'platform': platform.platform(),
                'processor': platform.processor(),
                'hostname': platform.node()
            }

            # 生成哈希
            machine_string = json.dumps(machine_info, sort_keys=True)
            machine_hash = hashlib.sha256(machine_string.encode()).hexdigest()

            return machine_hash[:16].upper()
        except Exception:
            # 如果获取硬件信息失败，使用备用方案
            fallback_info = f"{uuid.getnode()}-{platform.node()}"
            return hashlib.sha256(fallback_info.encode()).hexdigest()[:16].upper()

    def _load_feature_flags(self) -> Dict[str, Any]:
        """加载功能标志"""
        license_info = self.load_license()

        if not license_info:
            # 免费版功能限制
            return {
                'plan_type': 'free',
                'can_view_version_info': True,     # 基础功能：查看版本基本信息
                'can_open_file_content': False,   # 高级功能：打开文件内容
                'can_compare_versions': False,
                'can_export_version': False,
                'max_projects': float('inf'),  # 根据需求改为无限制
                'is_trial': False,
                'trial_days_left': 0,
                'is_activated': False
            }

        if license_info.get('plan_type') == 'vip':
            # VIP版所有功能开放
            return {
                'plan_type': 'vip',
                'can_view_version_info': True,     # 基础功能：查看版本基本信息
                'can_open_file_content': True,    # 高级功能：打开文件内容
                'can_compare_versions': True,
                'can_export_version': True,
                'max_projects': float('inf'),
                'is_trial': False,
                'trial_days_left': 0,
                'is_activated': True
            }

        # 默认返回免费版
        return self._load_feature_flags()

    def can_view_file_content(self) -> bool:
        """检查是否可以查看文件内容（向后兼容）"""
        return self.feature_flags.get('can_open_file_content', False)

    def load_license(self) -> Optional[Dict[str, Any]]:
        """加载许可证信息"""
        try:
            if os.path.exists(self.license_file):
                with open(self.license_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return None

    def is_vip_user(self) -> bool:
        """检查是否为VIP用户"""
        license_info = self.load_license()
        if not license_info:
            return False

        # 检查机器绑定
        if license_info.get('machine_id') != self.machine_id:
            return False

        # 验证签名
        activation_code = license_info.get('activation_code')
        user_email = license_info.get('user_email')
        plan_type = license_info.get('plan_type')
        signature = license_info.get('signature')

        if not all([activation_code, user_email, plan_type, signature]):
            return False

        expected_signature = self._generate_signature(activation_code, user_email, plan_type)
        return signature == expected_signature

    def can_use_feature(self, feature_name: str) -> bool:
        """检查是否可以使用某个功能"""
        return self.feature_flags.get(feature_name, False)

    def get_plan_type(self) -> str:
        """获取当前计划类型"""
        return self.feature_flags.get('plan_type', 'free')

    def is_activated(self) -> bool:
        """检查是否已激活"""
        return self.feature_flags.get('is_activated', False)

    def activate_vip_license(self, activation_code: str, user_email: str) -> Tuple[bool, str]:
        """激活VIP许可证

        Args:
            activation_code: 激活码
            user_email: 用户邮箱

        Returns:
            (是否成功, 消息)
        """
        try:
            # 验证激活码格式
            if not self._validate_activation_code_format(activation_code):
                return False, "激活码格式无效，请检查输入是否正确"

            # 解析激活码
            parts = activation_code.split('-')
            if len(parts) != 4 or parts[0] != "VMN" or parts[1] != "VIP":
                return False, "这不是有效的VIP激活码"

            random_part = parts[2]
            user_hash = parts[3]

            # 验证用户邮箱哈希
            expected_user_hash = hashlib.sha256((user_email + self.secret_key).encode()).hexdigest()[:8].upper()
            if user_hash != expected_user_hash:
                return False, "激活码与用户邮箱不匹配"

            # 检查是否已经激活过
            if self.is_vip_user():
                license_info = self.load_license()
                # 如果输入的激活码与当前激活码相同，说明是重新激活
                if license_info and license_info.get('activation_code') == activation_code:
                    return True, "该激活码已经在此设备上激活过了"
                else:
                    return False, "此设备已经激活过其他VIP激活码"

            # 创建VIP许可证
            license_info = {
                'activation_code': activation_code,
                'user_email': user_email,
                'plan_type': 'vip',
                'machine_id': self.machine_id,
                'activated_at': datetime.now().isoformat(),
                'signature': self._generate_signature(activation_code, user_email, 'vip')
            }

            # 保存许可证
            self._save_license(license_info)

            # 重新加载功能标志
            self.feature_flags = self._load_feature_flags()

            return True, "VIP激活成功！感谢您的支持！现在可以使用所有高级功能了。"

        except Exception as e:
            return False, f"激活失败：{str(e)}"

    def _validate_activation_code_format(self, activation_code: str) -> bool:
        """验证激活码格式"""
        if not activation_code:
            return False

        parts = activation_code.split('-')
        if len(parts) != 4:
            return False

        if parts[0] != "VMN" or parts[1] != "VIP":
            return False

        # 检查各部分长度
        if len(parts[2]) != 4 or len(parts[3]) != 8:
            return False

        # 检查是否为十六进制
        try:
            int(parts[2], 16)
            int(parts[3], 16)
            return True
        except ValueError:
            return False

    def _generate_signature(self, activation_code: str, user_email: str, plan_type: str) -> str:
        """生成数字签名"""
        data = f"{activation_code}:{user_email}:{plan_type}:{self.secret_key}"
        signature = hmac.new(
            self.secret_key.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()

        return signature[:16].upper()

    def _save_license(self, license_info: Dict[str, Any]) -> None:
        """保存许可证到本地"""
        try:
            # 创建备份
            if os.path.exists(self.license_file):
                backup_file = self.license_file + '.backup'
                try:
                    import shutil
                    shutil.copy2(self.license_file, backup_file)
                except:
                    pass

            # 保存新许可证
            with open(self.license_file, 'w', encoding='utf-8') as f:
                json.dump(license_info, f, indent=2, ensure_ascii=False)

        except Exception as e:
            raise Exception(f"保存许可证失败：{str(e)}")

    def clear_license(self) -> None:
        """清除许可证信息（用于调试或重置）"""
        try:
            if os.path.exists(self.license_file):
                os.remove(self.license_file)

            # 重新加载功能标志
            self.feature_flags = self._load_feature_flags()

        except Exception:
            pass

    def get_license_info(self) -> Optional[Dict[str, Any]]:
        """获取当前许可证信息"""
        if self.is_vip_user():
            return self.load_license()
        return None

    def check_activation_status(self) -> Dict[str, Any]:
        """检查激活状态"""
        if self.is_vip_user():
            license_info = self.load_license()
            return {
                'is_activated': True,
                'plan_type': 'vip',
                'user_email': license_info.get('user_email', ''),
                'activated_at': license_info.get('activated_at', ''),
                'machine_id': license_info.get('machine_id', ''),
                'features': self.feature_flags
            }
        else:
            return {
                'is_activated': False,
                'plan_type': 'free',
                'user_email': '',
                'activated_at': '',
                'machine_id': self.machine_id,
                'features': self.feature_flags
            }


class ActivationValidator:
    """激活码验证器（用于生成器）"""

    def __init__(self, secret_key: str = "verman_vip_secret_key_2024"):
        self.secret_key = secret_key

    def generate_vip_code(self, user_email: str) -> Tuple[str, Dict[str, Any]]:
        """生成VIP激活码

        Args:
            user_email: 用户邮箱

        Returns:
            (激活码, 激活码记录)
        """
        try:
            import secrets

            # 生成随机部分
            random_part = secrets.token_hex(2).upper()

            # 生成用户哈希部分
            user_hash = hashlib.sha256((user_email + self.secret_key).encode()).hexdigest()[:8].upper()

            # 组合激活码
            activation_code = f"VMN-VIP-{random_part}-{user_hash}"

            # 创建激活码记录
            record = {
                'activation_code': activation_code,
                'user_email': user_email,
                'plan_type': 'vip',
                'generated_at': datetime.now().isoformat(),
                'status': 'unused'
            }

            return activation_code, record

        except Exception as e:
            raise Exception(f"生成激活码失败：{str(e)}")

    def validate_activation_code(self, activation_code: str, user_email: str) -> bool:
        """验证激活码是否有效

        Args:
            activation_code: 激活码
            user_email: 用户邮箱

        Returns:
            是否有效
        """
        try:
            # 验证格式
            parts = activation_code.split('-')
            if len(parts) != 4 or parts[0] != "VMN" or parts[1] != "VIP":
                return False

            random_part = parts[2]
            user_hash = parts[3]

            # 验证用户哈希
            expected_user_hash = hashlib.sha256((user_email + self.secret_key).encode()).hexdigest()[:8].upper()
            return user_hash == expected_user_hash

        except Exception:
            return False


# 全局许可证管理器实例
license_manager = LicenseManager()