# -*- coding: utf-8 -*-
"""GUI 模块结构性测试：能 import + 能构造主窗 + YAML 渲染正确。

不会真正启动 ``mainloop``；如果当前环境无图形会话，自动跳过 Tk 部分。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

import yaml


def _has_display() -> bool:
    if sys.platform.startswith("win"):
        return True
    return bool(__import__("os").environ.get("DISPLAY"))


def test_gui_module_importable():
    """模块自身可独立 import（不依赖 paddleocr）。"""
    import camera_sync.gui  # noqa: F401


@pytest.mark.skipif(not _has_display(), reason="无图形会话")
def test_gui_construct_and_render_yaml(minimal_yaml: Path):
    import tkinter as tk

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk 不可用（CI 容器或纯字符终端）")

    try:
        root.withdraw()  # 不显示窗口
        from camera_sync.gui import CameraSyncGUI

        app = CameraSyncGUI(root, minimal_yaml)
        # 渲染当前界面状态为 YAML 文本，验证 round-trip 通过 yaml.safe_load
        text = app._render_yaml_text(persist=False)
        data = yaml.safe_load(text)

        # 关键 7 大节齐全
        for key in ("paths", "crop", "ocr", "runtime", "excel", "pipeline", "ui"):
            assert key in data, f"缺少节 {key}"

        # GUI 模式必须强制 pause_before_exit=False（避免工作线程被 input() 阻塞）
        assert data["ui"]["pause_before_exit"] is False

        # 路径与控件值一致
        assert data["paths"]["cr2_dir"]   == app.var_cr2.get()
        assert data["paths"]["jpg_dir"]   == app.var_jpg.get()
        assert data["paths"]["false_dir"] == app.var_false.get()

        # crop 数字类型，会被 YAML 序列化为整数
        assert data["crop"]["x"] == int(app.var_crop_x.get())
        assert data["crop"]["width"] == int(app.var_crop_w.get())

        # 写出 session yaml 并由 load_config 重新加载，端到端验证可被 pipeline 消费
        session = app._build_session_yaml()
        assert session.exists()
        from camera_sync.config import load_config
        cfg = load_config(session)
        assert cfg.ui.pause_before_exit is False
        assert cfg.crop.x == int(app.var_crop_x.get())

        session.unlink(missing_ok=True)
    finally:
        try:
            root.destroy()
        except Exception:
            pass
