"""
VIP激活码生成工具
供开发者使用的激活码生成和管理工具
"""

import os
import json
import hashlib
import secrets
from datetime import datetime
from typing import Dict, List, Optional, Tuple


class VIPActivationGenerator:
    """VIP激活码生成器"""

    def __init__(self, secret_key: str = "verman_vip_secret_key_2024"):
        """
        初始化激活码生成器

        Args:
            secret_key: 密钥，必须与license_manager.py中的密钥一致
        """
        self.secret_key = secret_key
        self.records_file = "data/vip_records.json"
        self._ensure_data_directory()

    def _ensure_data_directory(self):
        """确保数据目录存在"""
        os.makedirs(os.path.dirname(self.records_file), exist_ok=True)

    def generate_vip_code(self, user_email: str, notes: str = "") -> Tuple[str, Dict[str, any]]:
        """
        生成VIP激活码（与license_manager.py格式一致，使用一致性函数加密校验）

        Args:
            user_email: 用户邮箱（必填，用于一致性函数校验）
            notes: 备注信息

        Returns:
            (激活码, 激活码记录)
        """
        try:
            # 验证邮箱格式
            if not user_email or "@" not in user_email or "." not in user_email.split("@")[1]:
                raise ValueError("用户邮箱格式无效，请输入有效的邮箱地址")

            # 生成随机部分（4个字符）
            random_part = secrets.token_hex(2).upper()

            # 生成用户哈希部分（8个字符，基于用户邮箱和密钥的一致性函数）
            user_hash = hashlib.sha256((user_email + self.secret_key).encode()).hexdigest()[:8].upper()

            # 组合激活码：VMN-VIP-XXXX-XXXXXXXX（与license_manager.py一致）
            activation_code = f"VMN-VIP-{random_part}-{user_hash}"

            # 创建激活码记录
            record = {
                "activation_code": activation_code,
                "user_email": user_email,
                "plan_type": "vip",
                "generated_at": datetime.now().isoformat(),
                "status": "unused",
                "notes": notes,
                "random_part": random_part,
                "user_hash": user_hash
            }

            return activation_code, record

        except Exception as e:
            raise Exception(f"生成激活码失败: {str(e)}")

    def save_record(self, record: Dict[str, any]) -> bool:
        """
        保存激活码记录

        Args:
            record: 激活码记录

        Returns:
            是否保存成功
        """
        try:
            # 读取现有记录
            records = self.load_all_records()

            # 添加新记录
            records.append(record)

            # 保存到文件
            with open(self.records_file, 'w', encoding='utf-8') as f:
                json.dump(records, f, indent=2, ensure_ascii=False)

            return True

        except Exception as e:
            print(f"保存记录失败: {e}")
            return False

    def load_all_records(self) -> List[Dict[str, any]]:
        """
        加载所有激活码记录

        Returns:
            激活码记录列表
        """
        try:
            if os.path.exists(self.records_file):
                with open(self.records_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                return []
        except Exception as e:
            print(f"加载记录失败: {e}")
            return []

    def generate_and_save(self, user_email: str, user_id: str = "", notes: str = "") -> Optional[Tuple[str, Dict[str, any]]]:
        """
        生成激活码并保存记录

        Args:
            user_email: 用户邮箱（必填，用于生成激活码）
            user_id: 用户标识（可选，默认使用邮箱前缀）
            notes: 备注信息

        Returns:
            (激活码, 记录) 或 None
        """
        try:
            activation_code, record = self.generate_vip_code(user_email, notes)
            # 添加用户标识到记录中
            if not user_id:
                user_id = user_email.split("@")[0]  # 使用邮箱前缀作为默认用户ID
            record["user_id"] = user_id
            if self.save_record(record):
                return activation_code, record
            else:
                return None
        except Exception as e:
            print(f"生成并保存激活码失败: {e}")
            return None

    def mark_code_used(self, activation_code: str, machine_id: str, user_info: Dict[str, str]) -> bool:
        """
        标记激活码已使用

        Args:
            activation_code: 激活码
            machine_id: 机器ID
            user_info: 用户信息

        Returns:
            是否标记成功
        """
        try:
            records = self.load_all_records()

            for record in records:
                if record["activation_code"] == activation_code and record["status"] == "unused":
                    record["status"] = "used"
                    record["machine_id"] = machine_id
                    record["activated_at"] = datetime.now().isoformat()
                    record["activated_by"] = user_info.get("user_id", "unknown")
                    break

            # 保存更新的记录
            with open(self.records_file, 'w', encoding='utf-8') as f:
                json.dump(records, f, indent=2, ensure_ascii=False)

            return True

        except Exception as e:
            print(f"标记激活码失败: {e}")
            return False

    def get_unused_codes(self) -> List[Dict[str, any]]:
        """
        获取未使用的激活码

        Returns:
            未使用的激活码列表
        """
        records = self.load_all_records()
        return [r for r in records if r["status"] == "unused"]

    def get_used_codes(self) -> List[Dict[str, any]]:
        """
        获取已使用的激活码

        Returns:
            已使用的激活码列表
        """
        records = self.load_all_records()
        return [r for r in records if r["status"] == "used"]

    def search_records(self, keyword: str) -> List[Dict[str, any]]:
        """
        搜索激活码记录

        Args:
            keyword: 搜索关键词

        Returns:
            匹配的记录列表
        """
        records = self.load_all_records()
        keyword = keyword.lower()

        matched_records = []
        for record in records:
            if (keyword in record["activation_code"].lower() or
                keyword in record.get("user_id", "").lower() or
                keyword in record.get("notes", "").lower() or
                keyword in record.get("activated_by", "").lower()):
                matched_records.append(record)

        return matched_records

    def export_records(self, filename: str = "vip_records_export.json") -> bool:
        """
        导出激活码记录

        Args:
            filename: 导出文件名

        Returns:
            是否导出成功
        """
        try:
            records = self.load_all_records()

            # 添加统计信息
            export_data = {
                "export_info": {
                    "exported_at": datetime.now().isoformat(),
                    "total_records": len(records),
                    "unused_count": len([r for r in records if r["status"] == "unused"]),
                    "used_count": len([r for r in records if r["status"] == "used"])
                },
                "records": records
            }

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            return True

        except Exception as e:
            print(f"导出记录失败: {e}")
            return False

    def validate_activation_code(self, activation_code: str) -> bool:
        """
        验证激活码是否有效（与license_manager.py格式一致）

        Args:
            activation_code: 激活码

        Returns:
            是否有效
        """
        try:
            # 验证格式：VMN-VIP-XXXX-XXXXXXXX
            parts = activation_code.split('-')
            if len(parts) != 4 or parts[0] != "VMN" or parts[1] != "VIP":
                return False

            random_part = parts[2]  # 随机部分
            user_hash = parts[3]    # 用户哈希部分

            # 验证各部分长度
            if len(random_part) != 4 or len(user_hash) != 8:
                return False

            # 检查是否为十六进制
            try:
                int(random_part, 16)
                int(user_hash, 16)
                return True
            except ValueError:
                return False

        except Exception:
            return False

    def validate_activation_code_detailed(self, activation_code: str) -> Dict[str, any]:
        """
        详细验证激活码并返回验证结果信息

        Args:
            activation_code: 激活码

        Returns:
            验证结果字典，包含:
            - valid: 是否有效
            - reason: 验证结果原因
            - record: 激活码记录（如果存在）
        """
        result = {
            "valid": False,
            "reason": "",
            "record": None
        }

        try:
            # 1. 验证格式
            parts = activation_code.split('-')
            if len(parts) != 4 or parts[0] != "VMN" or parts[1] != "VIP":
                result["reason"] = "激活码格式无效，应为 VMN-VIP-XXXX-XXXXXXXX"
                return result

            random_part = parts[2]
            user_hash = parts[3]

            # 验证各部分长度
            if len(random_part) != 4 or len(user_hash) != 8:
                result["reason"] = "激活码格式无效，各部分长度不正确"
                return result

            # 检查是否为十六进制
            try:
                int(random_part, 16)
                int(user_hash, 16)
            except ValueError:
                result["reason"] = "激活码格式无效，包含非十六进制字符"
                return result

            # 2. 验证激活码是否存在
            records = self.load_all_records()
            for record in records:
                if record["activation_code"] == activation_code:
                    result["record"] = record

                    # 3. 检查状态
                    if record["status"] == "unused":
                        result["valid"] = True
                        result["reason"] = "激活码有效"
                    else:
                        result["reason"] = f"激活码已被使用，使用时间: {record.get('activated_at', '未知')}"
                    return result

            # 激活码不存在
            result["reason"] = "激活码不存在，请检查输入是否正确"
            return result

        except Exception as e:
            result["reason"] = f"验证过程中发生错误: {str(e)}"
            return result

    def generate_batch_codes(self, count: int = 10, prefix_id: str = "batch") -> List[Tuple[str, Dict[str, any]]]:
        """
        批量生成激活码（保持向后兼容性）

        Args:
            count: 生成数量
            prefix_id: 用户ID前缀

        Returns:
            激活码列表
        """
        return self.generate_batch_codes_with_domain(count, prefix_id, "verman.local", "批量生成")

    def generate_batch_codes_with_domain(self, count: int = 10, prefix_id: str = "batch", domain: str = "verman.local", notes: str = "批量生成") -> List[Tuple[str, Dict[str, any]]]:
        """
        批量生成激活码（支持自定义域名）

        Args:
            count: 生成数量
            prefix_id: 用户ID前缀
            domain: 邮箱域名
            notes: 备注信息

        Returns:
            激活码列表
        """
        codes = []
        for i in range(count):
            user_id = f"{prefix_id}{i+1}"
            user_email = f"{user_id}@{domain}"
            try:
                activation_code, record = self.generate_vip_code(user_email, f"{notes}第{i+1}个")
                # 添加用户标识到记录中
                record["user_id"] = user_id
                codes.append((activation_code, record))
            except Exception as e:
                print(f"生成第{i+1}个激活码失败: {e}")

        return codes

    def get_statistics(self) -> Dict[str, any]:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        records = self.load_all_records()

        total = len(records)
        unused = len([r for r in records if r["status"] == "unused"])
        used = len([r for r in records if r["status"] == "used"])

        return {
            "total_codes": total,
            "unused_codes": unused,
            "used_codes": used,
            "usage_rate": f"{(used/total*100):.1f}%" if total > 0 else "0%",
            "last_generated": records[-1]["generated_at"] if records else None
        }


def main():
    """命令行界面"""
    import sys

    print("=" * 50)
    print("🔑 VerMan VIP激活码生成工具")
    print("=" * 50)

    generator = VIPActivationGenerator()

    while True:
        print("\n请选择操作:")
        print("1. 生成单个激活码")
        print("2. 批量生成激活码")
        print("3. 查看统计信息")
        print("4. 搜索记录")
        print("5. 查看未使用激活码")
        print("6. 导出记录")
        print("7. 标记激活码已使用")
        print("8. 验证激活码")
        print("0. 退出")

        choice = input("\n请输入选项 (0-8): ").strip()

        if choice == "0":
            print("再见！")
            break

        elif choice == "1":
            # 生成单个激活码
            while True:
                user_email = input("请输入用户邮箱 (必填): ").strip()
                if not user_email:
                    print("❌ 邮箱不能为空!")
                    continue
                if "@" not in user_email or "." not in user_email.split("@")[1]:
                    print("❌ 邮箱格式无效，请输入有效的邮箱地址!")
                    continue
                break

            notes = input("请输入备注信息 (可选): ").strip()
            result = generator.generate_and_save(user_email, user_email.split("@")[0], notes)
            if result:
                activation_code, record = result
                print(f"\n✅ 激活码生成成功!")
                print(f"激活码: {activation_code}")
                print(f"用户邮箱: {user_email}")
                print(f"生成时间: {record['generated_at']}")
            else:
                print("❌ 生成失败!")

        elif choice == "2":
            # 批量生成激活码
            try:
                count = int(input("请输入生成数量: ").strip())
                domain = input("请输入邮箱域名 (默认: verman.local): ").strip() or "verman.local"
                prefix = input("请输入邮箱前缀 (默认: batch): ").strip() or "batch"
                notes = input("请输入备注信息 (可选): ").strip()

                if count > 0:
                    codes = generator.generate_batch_codes_with_domain(count, prefix, domain, notes)

                    # 保存所有记录
                    saved_count = 0
                    for activation_code, record in codes:
                        if generator.save_record(record):
                            saved_count += 1
                        print(f"激活码: {activation_code} (邮箱: {record['user_email']})")

                    print(f"\n✅ 成功生成并保存 {saved_count} 个激活码!")
                else:
                    print("❌ 数量必须大于0!")
            except ValueError:
                print("❌ 请输入有效的数字!")

        elif choice == "3":
            # 查看统计信息
            stats = generator.get_statistics()
            print(f"\n📊 统计信息:")
            print(f"总激活码数: {stats['total_codes']}")
            print(f"未使用: {stats['unused_codes']}")
            print(f"已使用: {stats['used_codes']}")
            print(f"使用率: {stats['usage_rate']}")
            if stats['last_generated']:
                print(f"最后生成: {stats['last_generated']}")

        elif choice == "4":
            # 搜索记录
            keyword = input("请输入搜索关键词: ").strip()
            if keyword:
                results = generator.search_records(keyword)
                print(f"\n🔍 搜索结果 ({len(results)} 条):")
                for record in results:
                    status = "✅ 已使用" if record["status"] == "used" else "🆓 未使用"
                    user_id = record.get("user_id", "default")
                    print(f"{status} | {record['activation_code']} | {user_id}")
                    if record.get("notes"):
                        print(f"    备注: {record['notes']}")
            else:
                print("❌ 请输入搜索关键词!")

        elif choice == "5":
            # 查看未使用激活码
            unused_codes = generator.get_unused_codes()
            print(f"\n🆓 未使用激活码 ({len(unused_codes)} 条):")
            for record in unused_codes:
                user_id = record.get("user_id", "default")
                print(f"{record['activation_code']} | {user_id} | {record['generated_at'][:19]}")
                if record.get("notes"):
                    print(f"    备注: {record['notes']}")

        elif choice == "6":
            # 导出记录
            filename = input("请输入导出文件名 (默认: vip_records_export.json): ").strip()
            filename = filename or "vip_records_export.json"

            if generator.export_records(filename):
                print(f"✅ 记录已导出到: {filename}")
            else:
                print("❌ 导出失败!")

        elif choice == "7":
            # 标记激活码已使用
            activation_code = input("请输入激活码: ").strip().upper()
            machine_id = input("请输入机器ID: ").strip()
            user_id = input("请输入用户标识 (可选): ").strip()

            if activation_code and machine_id:
                if not user_id:
                    user_id = "unknown"
                user_info = {"user_id": user_id}
                if generator.mark_code_used(activation_code, machine_id, user_info):
                    print(f"✅ 激活码 {activation_code} 已标记为使用!")
                else:
                    print("❌ 标记失败或激活码不存在!")
            else:
                print("❌ 请输入激活码和机器ID!")

        elif choice == "8":
            # 验证激活码
            activation_code = input("请输入激活码: ").strip().upper()

            if activation_code:
                if generator.validate_activation_code(activation_code):
                    print("✅ 激活码格式有效!")
                else:
                    print("❌ 激活码格式无效!")
            else:
                print("❌ 请输入激活码!")

        else:
            print("❌ 无效选项!")


if __name__ == "__main__":
    main()