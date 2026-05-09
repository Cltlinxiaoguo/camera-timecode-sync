# -*- coding: utf-8 -*-
"""Pipeline 端到端 smoke：用 monkeypatch 替换 PaddleOCR / rawpy 等重依赖。

策略：
1. 关闭 do_cr2_to_jpg 这一步（避免依赖 rawpy / 真实 CR2）；
2. 直接在 jpg_dir 放假 jpg 文件；
3. mock ``camera_sync.ocr_report.run_ocr_and_report`` 使其用预设结果直接走 ``write_report``，
   绕过 PaddleOCR；
4. 验证最终落盘 Excel 与 false 目录复制行为。
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from camera_sync import pipeline as pipeline_mod
from camera_sync.excel_writer import write_report


def _fake_run_ocr_and_report(cfg):
    # 模拟 OCR 后的结果直接写出 Excel
    results = {
        "img_001.jpg": ["00:01:02:03", "00:01:02:03"],   # True
        "img_002.jpg": ["00:01:02:03", "00:01:02:99"],   # False
        "img_003.jpg": [],                                # False
    }
    return write_report(
        results=results,
        excel_dir=cfg.paths.excel_dir,
        prefix=cfg.excel.filename_prefix,
        highlight_color=cfg.excel.highlight_color,
        now=datetime(2026, 5, 8, 13, 14, 15),
        insert_chart=False,
    )


def test_pipeline_run_uses_mocked_ocr(monkeypatch, minimal_yaml: Path, tmp_workspace: Path):
    pytest.importorskip("openpyxl")

    # 1. 在 jpg_dir 放 3 个假 JPG，否则 copy_false 阶段无源文件
    jpg_dir = tmp_workspace / "jpg"
    for name in ("img_001.jpg", "img_002.jpg", "img_003.jpg"):
        (jpg_dir / name).write_bytes(b"x")

    # 2. mock 掉 OCR 步骤
    monkeypatch.setattr(pipeline_mod, "run_ocr_and_report", _fake_run_ocr_and_report)

    # 3. 关闭 cr2_to_jpg / clear_jpg_dir（不删 mock 用的 jpg）
    yaml_text = minimal_yaml.read_text(encoding="utf-8")
    yaml_text = yaml_text.replace(
        "do_clear_jpg_dir: true", "do_clear_jpg_dir: false"
    ).replace(
        "do_cr2_to_jpg: true", "do_cr2_to_jpg: false"
    )
    minimal_yaml.write_text(yaml_text, encoding="utf-8")

    code = pipeline_mod.run(minimal_yaml)
    assert code == 0

    excel = tmp_workspace / "excel" / "Sync_n_Timecode_20260508_131415.xlsx"
    assert excel.exists()

    # img_002 / img_003 应被复制到 false
    false_dir = tmp_workspace / "false"
    assert (false_dir / "img_002.jpg").exists()
    assert (false_dir / "img_003.jpg").exists()
    assert not (false_dir / "img_001.jpg").exists()


def test_pipeline_returns_nonzero_when_ocr_yields_no_excel(monkeypatch, minimal_yaml: Path, tmp_workspace: Path):
    """OCR 步骤返回 None（无 jpg）时主流程退出码应为 4。"""
    monkeypatch.setattr(pipeline_mod, "run_ocr_and_report", lambda cfg: None)

    # 关闭 cr2_to_jpg 以免依赖 rawpy
    yaml_text = minimal_yaml.read_text(encoding="utf-8")
    yaml_text = yaml_text.replace("do_cr2_to_jpg: true", "do_cr2_to_jpg: false")
    minimal_yaml.write_text(yaml_text, encoding="utf-8")

    code = pipeline_mod.run(minimal_yaml)
    assert code == 4


def test_pipeline_handles_config_error(tmp_path: Path):
    """加载阶段失败时应返回 2 且不抛异常。"""
    bad = tmp_path / "broken.yaml"
    bad.write_text("paths: not-a-dict", encoding="utf-8")
    code = pipeline_mod.run(bad)
    assert code == 2
