import os
import sys
import threading
import time
import shutil
from pathlib import Path

# Add the project root to sys.path if not frozen
if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.utils import get_app_dir, get_data_dir

def initialize_user_data():
    """初始化用户数据目录（如果是第一次运行，复制默认配置）"""
    data_dir = get_data_dir()
    app_dir = get_app_dir()
    
    # 确保 data 目录和 audio 目录存在
    (data_dir / "data").mkdir(parents=True, exist_ok=True)
    (data_dir / "static" / "audio").mkdir(parents=True, exist_ok=True)
    
    # 初始化 styles.yaml
    config_dir = data_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    styles_dest = config_dir / "styles.yaml"
    styles_src = app_dir / "config" / "styles.yaml"
    
    if not styles_dest.exists() and styles_src.exists():
        shutil.copy2(styles_src, styles_dest)
        
    # 初始化 .env (可选，如果有 .env.example 可以复制一个默认的)
    env_dest = data_dir / ".env"
    env_src = app_dir / ".env.example"
    if not env_dest.exists() and env_src.exists():
        shutil.copy2(env_src, env_dest)

def start_server():
    import uvicorn
    from app.main import app
    # Start FastAPI server
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")

def main():
    initialize_user_data()
    
    # 确保自带的 ffmpeg.exe 能被找到
    data_dir = get_data_dir()
    os.environ["PATH"] = str(data_dir) + os.pathsep + os.environ.get("PATH", "")
    
    # Use pywebview to create a desktop window
    import webview
    
    # Start server in daemon thread
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    # Wait briefly to let server initialize
    time.sleep(1.5)
    
    # Create window
    window = webview.create_window(
        title='AI 音乐生成器 - 景德镇',
        url='http://127.0.0.1:8000',
        width=1024,
        height=768,
        resizable=True,
        text_select=True,
        confirm_close=True
    )
    
    # Start the webview loop
    webview.start()

if __name__ == '__main__':
    # For multiprocessing/PyInstaller compatibility
    import multiprocessing
    multiprocessing.freeze_support()
    main()