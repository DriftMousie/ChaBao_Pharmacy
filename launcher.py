from __future__ import annotations

import os
import socket
import sys
from pathlib import Path


APP_NAME = "查宝（药店版）"
HOST = "127.0.0.1"
PORT = 8501


def _resource_root() -> Path:
    """兼容源码运行和 PyInstaller onefile 解压后的临时资源目录。"""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


def _app_path() -> Path:
    return _resource_root() / "app.py"


def _workspace_root() -> Path:
    """用户业务工作目录。onefile 打包后使用 exe 所在目录，而不是 _MEIPASS 临时目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _is_port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def _print_access_message(url: str) -> None:
    print()
    print("=" * 60)
    print(f"{APP_NAME} 已准备启动")
    print("请不要关闭这个黑色窗口；关闭窗口会停止程序。")
    print()
    print("请手动打开浏览器，并在地址栏输入：")
    print()
    print(f"    {url}")
    print()
    print("如果页面暂时打不开，请等待 10-30 秒后刷新。")
    print("=" * 60)
    print()


def main() -> int:
    app_path = _app_path()
    if not app_path.exists():
        print(f"未找到程序入口：{app_path}")
        print("请确认打包时已包含 app.py。")
        input("按回车键退出...")
        return 1

    url = f"http://{HOST}:{PORT}"
    if _is_port_open(HOST, PORT):
        print(f"端口 {PORT} 已经有本地服务在运行。")
        _print_access_message(url)
        input("按回车键退出当前启动器...")
        return 0

    os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"
    os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    os.environ["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"
    os.environ["CHABAO_WORKSPACE"] = str(_workspace_root())

    _print_access_message(url)

    # PyInstaller onefile 中不要再用 subprocess 调用 sys.executable -m streamlit。
    # 打包后 sys.executable 指向当前 exe，自启动子进程容易导致 Streamlit 没有真正启动而超时。
    # 直接调用 Streamlit CLI 主函数，让服务在当前进程内运行，更适合单文件 exe。
    try:
        from streamlit.web import cli as stcli
    except Exception as exc:
        print("无法导入 Streamlit 启动模块。")
        print(f"错误信息：{exc}")
        input("按回车键退出...")
        return 1

    sys.argv = [
        "streamlit",
        "run",
        str(app_path),
        "--global.developmentMode",
        "false",
        "--server.address",
        HOST,
        "--server.port",
        str(PORT),
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]

    try:
        stcli.main()
    except KeyboardInterrupt:
        print("程序已停止。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
