# -*- coding: utf-8 -*-
"""相机同步检测工具 入口（PyInstaller onefile 主程序）。

行为：
- 双击 exe（无参数）  → 启动 Tkinter GUI；
- ``exe --cli``       → 控制台模式，自动加载同目录 ``camera_sync_config.yaml``；
- ``exe --cli <path>`` → 控制台模式，使用指定 YAML；
- ``exe <path>``      → GUI 模式，使用指定 YAML 作为初值；
- ``exe --help``      → 打印简短帮助。

通用：
- multiprocessing 在 Windows 下需要 ``freeze_support()``；
- 所有日志统一 UTF-8；控制台同时输出到 ``logs/run_<timestamp>.log``；
- 控制台模式结束时按 YAML ``ui.pause_before_exit`` 决定是否提示按回车退出。
"""
from __future__ import annotations

import multiprocessing
import sys
from typing import List, Optional


HELP = """\
相机同步检测工具 — 命令行帮助

用法:
  相机同步检测工具.exe                      启动图形界面（GUI）
  相机同步检测工具.exe <yaml>               GUI 启动并以 <yaml> 作为初值
  相机同步检测工具.exe --cli                控制台模式，使用同目录 camera_sync_config.yaml
  相机同步检测工具.exe --cli <yaml>         控制台模式并指定 YAML
  相机同步检测工具.exe --help / -h          显示本帮助

退出码:
  0    成功
  1    流水线异常
  2    配置加载失败
  3    CR2 转 JPG 全部失败
  4    OCR 没有输入或未生成 Excel
  5    GUI 初始化失败（无图形会话），请用 --cli
  130  用户 Ctrl+C
"""


def _parse_args(argv: List[str]) -> tuple[bool, Optional[str], bool]:
    """返回 (cli_mode, yaml_path, want_help)。"""
    cli_mode = False
    yaml_path: Optional[str] = None
    want_help = False
    rest = list(argv)
    while rest:
        a = rest.pop(0)
        if a in ("--help", "-h", "/?"):
            want_help = True
        elif a == "--cli":
            cli_mode = True
        elif a.startswith("-"):
            sys.stderr.write(f"未知参数: {a}\n")
            want_help = True
        else:
            yaml_path = a
    return cli_mode, yaml_path, want_help


def main() -> int:
    multiprocessing.freeze_support()  # PyInstaller + Windows 多进程必备

    cli_mode, yaml_path, want_help = _parse_args(sys.argv[1:])

    if want_help:
        sys.stdout.write(HELP)
        return 0

    if cli_mode:
        from camera_sync.pipeline import run as pipeline_run
        return pipeline_run(yaml_path)

    # 默认走 GUI；若 Tk 不可用（如远程 SSH 无显示），自动回退控制台
    from camera_sync.gui import run_gui
    code = run_gui(yaml_path)
    if code == 5:
        from camera_sync.pipeline import run as pipeline_run
        return pipeline_run(yaml_path)
    return code


if __name__ == "__main__":
    sys.exit(main())
