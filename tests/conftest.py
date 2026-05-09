# -*- coding: utf-8 -*-
"""pytest 通用 fixture：临时目录、最小可用配置、logger 隔离等。

不在此处导入 paddleocr / rawpy / cv2，避免没装这些库时 collection 失败。
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

# 让 tests 内部能 ``import camera_sync.*``
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _isolate_camera_sync_logger():
    """每个用例开始前把 ``camera_sync`` logger 重置到干净状态。

    背景：``setup_logging`` 会在 ``camera_sync`` 上设 ``propagate=False``，
    若一个用例触发了它，后续用例里 pytest 的 ``caplog`` (默认挂 root) 就
    抓不到 ``camera_sync.xxx`` 的日志。autouse fixture 隔离测试间副作用。
    """
    cam = logging.getLogger("camera_sync")
    saved_handlers = list(cam.handlers)
    saved_level = cam.level
    saved_propagate = cam.propagate

    for h in saved_handlers:
        cam.removeHandler(h)
    cam.setLevel(logging.NOTSET)
    cam.propagate = True
    try:
        yield
    finally:
        for h in list(cam.handlers):
            cam.removeHandler(h)
            try:
                h.close()
            except Exception:
                pass
        for h in saved_handlers:
            cam.addHandler(h)
        cam.setLevel(saved_level)
        cam.propagate = saved_propagate


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Path:
    """提供一个含 cr2/jpg/false/excel/log 五个子目录的临时工作区。"""
    for sub in ("cr2", "jpg", "false", "excel", "logs"):
        (tmp_path / sub).mkdir()
    return tmp_path


@pytest.fixture
def minimal_yaml(tmp_workspace: Path) -> Path:
    """写出一个最小可用 YAML 并返回其路径。"""
    yaml_path = tmp_workspace / "camera_sync_config.yaml"
    yaml_path.write_text(
        f"""
paths:
  cr2_dir: '{(tmp_workspace / 'cr2').as_posix()}'
  jpg_dir: '{(tmp_workspace / 'jpg').as_posix()}'
  false_dir: '{(tmp_workspace / 'false').as_posix()}'
  excel_dir: '{(tmp_workspace / 'excel').as_posix()}'
  log_dir: '{(tmp_workspace / 'logs').as_posix()}'
crop:
  x: 10
  y: 20
  width: 100
  height: 50
ocr:
  lang: 'ch'
  use_gpu: false
  timecode_regex: '\\d{{2}}:\\d{{2}}:\\d{{2}}:\\d{{2}}'
  force_hour_zero: true
runtime:
  max_workers: 0
  fail_fast_on_ocr_error: false
excel:
  filename_prefix: 'Sync_n_Timecode'
  highlight_color: 'FFCCCC'
pipeline:
  do_clear_jpg_dir: true
  do_cr2_to_jpg: true
  do_ocr_report: true
  do_clear_false_dir: true
  do_copy_false: true
ui:
  pause_before_exit: false
""".strip(),
        encoding="utf-8",
    )
    return yaml_path
