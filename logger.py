"""
统一日志和错误处理模块
提供一致的日志记录和错误报告功能
"""

import logging
import os
import sys
import json
from datetime import datetime
from typing import Optional, List, Dict
import traceback


class VerManLogger:
    """VerMan专用日志记录器"""

    def __init__(self, name: str = "verman"):
        """初始化日志记录器"""
        self.logger = logging.getLogger(name)
        self._setup_logger()

    def _setup_logger(self):
        """设置日志配置"""
        if self.logger.handlers:
            return  # 已经配置过

        self.logger.setLevel(logging.DEBUG)

        # 创建日志目录
        log_dir = os.path.join(os.path.expanduser("~"), ".verman", "logs")
        os.makedirs(log_dir, exist_ok=True)

        # 日志文件路径
        log_file = os.path.join(log_dir, f"verman_{datetime.now().strftime('%Y%m%d')}.log")

        # 文件处理器
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)

        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)

        # 格式化器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # 添加处理器
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def debug(self, message: str, exc_info: Optional[Exception] = None):
        """调试日志"""
        if exc_info:
            self.logger.debug(message, exc_info=exc_info)
        else:
            self.logger.debug(message)

    def info(self, message: str):
        """信息日志"""
        self.logger.info(message)

    def warning(self, message: str):
        """警告日志"""
        self.logger.warning(message)

    def error(self, message: str, exc_info: Optional[Exception] = None):
        """错误日志"""
        if exc_info:
            self.logger.error(message, exc_info=exc_info)
        else:
            self.logger.error(message)

    def critical(self, message: str, exc_info: Optional[Exception] = None):
        """严重错误日志"""
        if exc_info:
            self.logger.critical(message, exc_info=exc_info)
        else:
            self.logger.critical(message)


# 全局日志实例
logger = VerManLogger()


class VerManError(Exception):
    """VerMan自定义异常基类"""

    def __init__(self, message: str, error_code: str = None, cause: Exception = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.cause = cause
        self.timestamp = datetime.now()

    def __str__(self):
        return self.message


class FileOperationError(VerManError):
    """文件操作异常"""
    pass


class DatabaseError(VerManError):
    """数据库操作异常"""
    pass


class VersionError(VerManError):
    """版本操作异常"""
    pass


class ValidationError(VerManError):
    """数据验证异常"""
    pass


def handle_error(error: Exception, context: str = "", user_message: str = None) -> str:
    """
    统一错误处理函数

    Args:
        error: 异常对象
        context: 错误上下文信息
        user_message: 用户友好的错误消息

    Returns:
        用户友好的错误消息
    """
    # 记录错误
    if isinstance(error, VerManError):
        logger.error(f"{context}: {error.message}", exc_info=error)
        base_message = error.message
    else:
        logger.error(f"{context}: {str(error)}", exc_info=error)
        base_message = str(error)

    # 返回用户友好的消息
    if user_message:
        return user_message
    elif isinstance(error, (FileNotFoundError, PermissionError)):
        return f"文件访问错误: {base_message}"
    elif isinstance(error, (DatabaseError, OSError)):
        return f"系统错误: {base_message}"
    elif isinstance(error, ValidationError):
        return f"数据验证错误: {base_message}"
    else:
        return f"操作失败: {base_message}"


def log_operation(operation: str, details: str = "", success: bool = True):
    """
    记录操作日志

    Args:
        operation: 操作名称
        details: 操作详情
        success: 操作是否成功
    """
    status = "成功" if success else "失败"
    message = f"操作{status}: {operation}"
    if details:
        message += f" - {details}"

    if success:
        logger.info(message)
    else:
        logger.warning(message)


def get_error_context() -> dict:
    """
    获取错误上下文信息

    Returns:
        包含错误上下文的字典
    """
    return {
        'timestamp': datetime.now().isoformat(),
        'working_directory': os.getcwd(),
        'python_version': sys.version,
        'traceback': traceback.format_exc() if sys.exc_info()[0] else None
    }


class OperationLogger:
    """操作日志记录器，用于记录用户操作历史"""

    def __init__(self):
        """初始化操作日志记录器"""
        self.log_file = os.path.join(os.path.expanduser("~"), ".verman", "operation_logs.json")
        self.max_logs = 500  # 最大保留日志条数
        self._load_logs()

    def _load_logs(self):
        """加载操作日志"""
        try:
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    self.logs = json.load(f)
            else:
                self.logs = []
        except Exception:
            self.logs = []

    def _save_logs(self):
        """保存操作日志"""
        try:
            # 确保目录存在
            log_dir = os.path.dirname(self.log_file)
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)

            # 限制日志数量
            if len(self.logs) > self.max_logs:
                self.logs = self.logs[-self.max_logs:]

            with open(self.log_file, 'w', encoding='utf-8') as f:
                json.dump(self.logs, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def log_operation(self, action: str, details: str = "", project_path: str = "", level: str = "INFO"):
        """记录操作日志

        Args:
            action: 操作类型
            details: 操作详情
            project_path: 项目路径
            level: 日志级别 (INFO, WARNING, ERROR)
        """
        log_entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "level": level.upper(),
            "action": action,
            "details": details,
            "project_path": project_path
        }

        self.logs.append(log_entry)
        self._save_logs()

    def log_project_created(self, project_path: str):
        """记录项目创建"""
        self.log_operation("创建项目", f"项目路径: {project_path}", project_path, "INFO")

    def log_project_opened(self, project_path: str):
        """记录项目打开"""
        self.log_operation("打开项目", f"项目路径: {project_path}", project_path, "INFO")

    def log_project_closed(self, project_path: str):
        """记录项目关闭"""
        self.log_operation("关闭项目", f"项目路径: {project_path}", project_path, "INFO")

    def log_version_created(self, version_number: str, description: str, file_count: int, project_path: str):
        """记录版本创建"""
        details = f"版本号: {version_number}, 描述: {description or '无描述'}, 文件数: {file_count}"
        self.log_operation("创建版本", details, project_path, "INFO")

    def log_version_rollback(self, version_number: str, backup: bool, project_path: str):
        """记录版本回滚"""
        details = f"回滚到版本: {version_number}, 备份: {'是' if backup else '否'}"
        self.log_operation("回滚版本", details, project_path, "WARNING")

    def log_version_exported(self, version_number: str, export_path: str, project_path: str):
        """记录版本导出"""
        details = f"版本号: {version_number}, 导出路径: {export_path}"
        self.log_operation("导出版本", details, project_path, "INFO")

    def log_error(self, action: str, error: str, project_path: str = ""):
        """记录错误"""
        self.log_operation(f"错误 - {action}", f"错误信息: {error}", project_path, "ERROR")

    def get_logs(self, limit: int = None) -> List[Dict]:
        """获取日志"""
        if limit:
            return self.logs[-limit:] if len(self.logs) > limit else self.logs
        return self.logs.copy()

    def clear_logs(self):
        """清空日志"""
        self.logs = []
        self._save_logs()

    def get_logs_by_project(self, project_path: str) -> List[Dict]:
        """获取指定项目的日志"""
        return [log for log in self.logs if log.get("project_path") == project_path]

    def get_logs_by_level(self, level: str) -> List[Dict]:
        """获取指定级别的日志"""
        return [log for log in self.logs if log.get("level") == level.upper()]


# 全局操作日志实例
operation_logger = OperationLogger()