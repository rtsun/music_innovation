import os
import sys
from pathlib import Path

def get_app_dir() -> Path:
    """获取程序静态资源所在的目录 (内嵌在 exe/app 中)"""
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            return Path(sys._MEIPASS)
        # Fallback for some macOS .app bundles
        return Path(sys.executable).parent.parent / "Resources"
    return Path(__file__).resolve().parent.parent

def get_data_dir() -> Path:
    """获取用户数据所在的目录 (持久化)"""
    if getattr(sys, 'frozen', False):
        if sys.platform == 'darwin':
            # macOS 下将数据放在用户的 Application Support 目录
            app_support = Path.home() / "Library" / "Application Support" / "MusicInnovationGenerator"
            app_support.mkdir(parents=True, exist_ok=True)
            return app_support
        # Windows: 与 exe 同级
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent