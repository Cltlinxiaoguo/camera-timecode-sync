# -*- coding: utf-8 -*-
"""日志初始化测试。"""
from __future__ import annotations

import logging
from pathlib import Path

from camera_sync.logging_setup import get_logger, setup_logging


def _flush_camera_sync():
    for h in logging.getLogger("camera_sync").handlers:
        h.flush()


def test_setup_logging_creates_file(tmp_path: Path):
    log_file = setup_logging(tmp_path)
    assert log_file.exists()
    log = get_logger("camera_sync.test")
    log.info("hello-utf8-中文")
    _flush_camera_sync()
    text = log_file.read_text(encoding="utf-8")
    assert "hello-utf8-中文" in text


def test_setup_logging_is_idempotent(tmp_path: Path):
    setup_logging(tmp_path)
    handlers_1 = list(logging.getLogger("camera_sync").handlers)
    setup_logging(tmp_path)
    handlers_2 = list(logging.getLogger("camera_sync").handlers)
    # 重复调用必须保持稳定的 handler 数（避免重复挂导致日志双写）
    assert len(handlers_1) == len(handlers_2) == 2  # console + file


def test_logging_isolated_from_root_level_changes(tmp_path: Path):
    """关键回归测试：模拟 paddle 把 root level 抬到 WARNING，
    我们在 camera_sync 自己的 logger 上仍要能记录 INFO 到文件。"""
    log_file = setup_logging(tmp_path)

    # 模拟 paddle/distributed/utils/log_utils.py 的副作用
    logging.getLogger().setLevel(logging.WARNING)

    log = get_logger("camera_sync.regression")
    log.info("must-survive-root-warning")
    _flush_camera_sync()

    text = log_file.read_text(encoding="utf-8")
    assert "must-survive-root-warning" in text, (
        "camera_sync 的 INFO 日志在 root=WARNING 后应该仍然写入文件"
    )
