import os
import sys
from pathlib import Path

def get_app_dir() -> Path:
    """获取程序静态资源所在的目录 (内嵌在 exe 中)"""
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent

def get_data_dir() -> Path:
    """获取用户数据所在的目录 (与 exe 同级，持久化)"""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent
