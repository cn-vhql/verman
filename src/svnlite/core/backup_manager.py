"""
备份管理类
"""
import os
import shutil
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from .models import Repository


class BackupManager:
    """备份管理类"""

    def __init__(self, repository: Repository):
        self.repository = repository

    def create_system_backup(self, description: str = "") -> Tuple[bool, str, Optional[str]]:
        """创建系统完整备份"""
        if not self.repository.is_repository():
            return False, "当前目录不是版本库", None

        backup_name = f"system_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup_path = self.repository.get_backup_path(backup_name)

        try:
            # 创建备份目录
            os.makedirs(backup_path, exist_ok=True)

            # 备份整个.svmini目录
            svmini_backup_path = os.path.join(backup_path, "svmini")
            if os.path.exists(self.repository.svmini_path):
                shutil.copytree(self.repository.svmini_path, svmini_backup_path)

            # 创建备份元数据
            backup_meta = {
                "type": "system",
                "name": backup_name,
                "description": description,
                "timestamp": datetime.now().isoformat(),
                "size": self._get_directory_size(svmini_backup_path) if os.path.exists(svmini_backup_path) else 0
            }

            meta_path = os.path.join(backup_path, "backup_meta.json")
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(backup_meta, f, indent=2, ensure_ascii=False)

            return True, f"系统备份创建成功: {backup_name}", backup_name

        except Exception as e:
            # 清理失败的备份
            if os.path.exists(backup_path):
                shutil.rmtree(backup_path)
            return False, f"创建系统备份失败: {str(e)}", None

    def list_backups(self) -> List[Dict]:
        """列出所有备份"""
        if not os.path.exists(self.repository.backups_path):
            return []

        backups = []
        try:
            for item in os.listdir(self.repository.backups_path):
                backup_path = os.path.join(self.repository.backups_path, item)
                if os.path.isdir(backup_path):
                    meta_path = os.path.join(backup_path, "backup_meta.json")
                    if os.path.exists(meta_path):
                        backup_info = self._load_backup_info(meta_path)
                        if backup_info:
                            backup_info["path"] = backup_path
                            backups.append(backup_info)

            # 按时间排序
            backups.sort(key=lambda x: x["timestamp"], reverse=True)

        except Exception:
            pass

        return backups

    def _load_backup_info(self, meta_path: str) -> Optional[Dict]:
        """加载备份信息"""
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)

            # 计算备份大小
            backup_dir = os.path.dirname(meta_path)
            size = self._get_directory_size(backup_dir)

            return {
                "name": meta.get("name", os.path.basename(os.path.dirname(meta_path))),
                "type": meta.get("type", "unknown"),
                "description": meta.get("description", ""),
                "timestamp": meta.get("timestamp"),
                "size": size,
                "files_count": meta.get("files_count", 0)
            }
        except Exception:
            return None

    def _get_directory_size(self, directory: str) -> int:
        """获取目录大小"""
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(directory):
                for filename in filenames:
                    file_path = os.path.join(dirpath, filename)
                    try:
                        total_size += os.path.getsize(file_path)
                    except OSError:
                        pass
        except Exception:
            pass
        return total_size

    def delete_backup(self, backup_name: str) -> Tuple[bool, str]:
        """删除备份"""
        backup_path = self.repository.get_backup_path(backup_name)

        if not os.path.exists(backup_path):
            return False, f"备份 {backup_name} 不存在"

        try:
            shutil.rmtree(backup_path)
            return True, f"备份 {backup_name} 已删除"
        except Exception as e:
            return False, f"删除备份失败: {str(e)}"