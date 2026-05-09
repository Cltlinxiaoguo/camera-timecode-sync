# -*- coding: utf-8 -*-
"""日志初始化：控制台 + 文件，UTF-8。

PRD 要求：
- 异常需"捕获并记录日志"避免无声崩溃；
- 控制台保留进度输出；
- 编码统一 UTF-8。
"""
from __future__ import annotations

import logging
import logging.handlers
import sys
from datetime import datetime
from pathlib import Path


_LOGGER_NAME = "camera_sync"
_FMT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"


def _configure_console_utf8() -> None:
    """让 Windows 控制台尽量支持 UTF-8 输出。"""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            # 老版本 Python / 已被替换的 stream，忽略
            pass


def setup_logging(log_dir: Path, level: int = logging.INFO) -> Path:
    """初始化全局日志：控制台 + 时间戳日志文件。

    返回实际写出的日志文件绝对路径。
    重复调用是幂等的（清空旧 handlers 再装）。

    设计要点（重要！踩过的坑）：
    --------------------------------------------------------------------
    - **不挂在 root logger 上**。paddle 在 import 时（`group_sharded.py`、
      `group_sharded_stage2.py` 等模块）调用 `paddle.distributed.utils
      .log_utils.get_logger(logging.WARNING)` —— 该函数 `name` 默认值就是
      字符串 `"root"`，等同于直接 `logging.getLogger().setLevel(WARNING)`。
      副作用：导入 paddleocr 后我们所有 INFO 消息会被 root 级别全拦。
    - 因此把 handlers 挂在专属的 ``camera_sync`` logger 上、并 ``propagate
      =False`` 阻断到 root 的传播。这样即使 paddle 把 root 拉到 WARNING，
      我们的 INFO 也照常打印 / 写文件。
    - 同步把 ``ppocr`` / ``matplotlib`` / ``PIL`` 级别压低，减少噪音。
    """
    _configure_console_utf8()

    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"run_{timestamp}.log"

    formatter = logging.Formatter(_FMT, datefmt=_DATEFMT)

    cam_logger = logging.getLogger(_LOGGER_NAME)
    for h in list(cam_logger.handlers):
        cam_logger.removeHandler(h)
    cam_logger.setLevel(level)
    cam_logger.propagate = False  # 关键：不让 root 的级别变化影响我们

    console = logging.StreamHandler(stream=sys.stdout)
    console.setLevel(level)
    console.setFormatter(formatter)
    cam_logger.addHandler(console)

    file_handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    cam_logger.addHandler(file_handler)

    # 第三方库静音
    logging.getLogger("ppocr").setLevel(logging.ERROR)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)

    return log_file


def get_logger(name: str = _LOGGER_NAME) -> logging.Logger:
    return logging.getLogger(name)
