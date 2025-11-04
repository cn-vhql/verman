"""
配置管理类
"""
import json
import os
from typing import Optional, List

from ..core.models import Config


class ConfigManager:
    """配置管理类"""

    def __init__(self, repository_path: str):
        self.repo_path = repository_path
        self.config_path = os.path.join(repository_path, '.svmini', 'config.json')
        self._config: Optional[Config] = None

    def load_config(self) -> Config:
        """加载配置"""
        if self._config is not None:
            return self._config

        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._config = Config.from_dict(data)
            except Exception:
                self._config = Config()  # 使用默认配置
        else:
            self._config = Config()  # 使用默认配置

        return self._config

    def save_config(self, config: Config) -> bool:
        """保存配置"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)
            self._config = config
            return True
        except Exception:
            return False

    def get_author(self) -> str:
        """获取提交者名称"""
        return self.load_config().author

    def set_author(self, author: str) -> bool:
        """设置提交者名称"""
        config = self.load_config()
        config.author = author
        return self.save_config(config)

    def reset_to_default(self) -> bool:
        """重置为默认配置"""
        default_config = Config()
        return self.save_config(default_config)