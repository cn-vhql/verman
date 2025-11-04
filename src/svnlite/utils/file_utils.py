"""
文件操作工具类
"""
import os
import hashlib
import shutil
from typing import Optional, List
from pathlib import Path


def calculate_file_hash(file_path: str) -> str:
    """计算文件的 SHA-256 哈希值"""
    hash_sha256 = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except (IOError, OSError):
        return ""


def get_file_size(file_path: str) -> int:
    """获取文件大小"""
    try:
        return os.path.getsize(file_path)
    except (IOError, OSError):
        return 0


def get_file_mtime(file_path: str) -> float:
    """获取文件最后修改时间"""
    try:
        return os.path.getmtime(file_path)
    except (IOError, OSError):
        return 0.0


def ensure_directory_exists(dir_path: str) -> bool:
    """确保目录存在"""
    try:
        os.makedirs(dir_path, exist_ok=True)
        return True
    except (IOError, OSError):
        return False


def copy_file_with_permissions(src: str, dst: str) -> bool:
    """复制文件并保留权限"""
    try:
        ensure_directory_exists(os.path.dirname(dst))
        shutil.copy2(src, dst)
        return True
    except (IOError, OSError):
        return False


def is_binary_file(file_path: str) -> bool:
    """判断是否为二进制文件"""
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(1024)
            return b'\0' in chunk
    except (IOError, OSError):
        return True


def read_text_file(file_path: str, encoding: str = 'utf-8') -> Optional[str]:
    """读取文本文件内容"""
    try:
        # 尝试多种编码
        encodings = [encoding, 'utf-8', 'gbk', 'latin-1']
        for enc in encodings:
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
        return None
    except (IOError, OSError):
        return None


def write_text_file(file_path: str, content: str, encoding: str = 'utf-8') -> bool:
    """写入文本文件"""
    try:
        ensure_directory_exists(os.path.dirname(file_path))
        with open(file_path, 'w', encoding=encoding) as f:
            f.write(content)
        return True
    except (IOError, OSError):
        return False


def find_files(directory: str, ignore_dirs: Optional[List[str]] = None) -> List[str]:
    """递归查找目录下的所有文件"""
    if ignore_dirs is None:
        ignore_dirs = ['.git', '.svn', '__pycache__', 'node_modules']

    files = []
    try:
        for root, dirs, filenames in os.walk(directory):
            # 过滤忽略的目录
            dirs[:] = [d for d in dirs if d not in ignore_dirs]

            for filename in filenames:
                file_path = os.path.join(root, filename)
                files.append(file_path)
    except (IOError, OSError):
        pass

    return files


def get_file_extension(file_path: str) -> str:
    """获取文件扩展名"""
    return os.path.splitext(file_path)[1].lower()


def is_text_file_by_extension(file_path: str) -> bool:
    """根据扩展名判断是否为文本文件"""
    text_extensions = {
        '.txt', '.py', '.js', '.html', '.css', '.xml', '.json',
        '.md', '.yml', '.yaml', '.ini', '.cfg', '.conf', '.log',
        '.sql', '.sh', '.bat', '.cmd', '.ps1', '.rb', '.php',
        '.java', '.c', '.cpp', '.h', '.hpp', '.cs', '.go',
        '.rs', '.swift', '.kt', '.scala', '.r', '.m', '.pl',
        '.vb', '.dart', '.ts', '.jsx', '.tsx', '.vue', '.svelte'
    }
    return get_file_extension(file_path) in text_extensions


def safe_remove_file(file_path: str) -> bool:
    """安全删除文件"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
        return True
    except (IOError, OSError):
        return False


def safe_remove_directory(dir_path: str) -> bool:
    """安全删除目录"""
    try:
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
        return True
    except (IOError, OSError):
        return False


def get_directory_size(directory: str) -> int:
    """获取目录总大小"""
    total_size = 0
    try:
        for dirpath, dirnames, filenames in os.walk(directory):
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                total_size += get_file_size(file_path)
    except (IOError, OSError):
        pass
    return total_size


def format_file_size(size_bytes: int) -> str:
    """格式化文件大小显示"""
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)

    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1

    return f"{size:.1f} {size_names[i]}"