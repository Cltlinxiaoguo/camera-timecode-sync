# -*- coding: utf-8 -*-
"""copy_false_images 测试：使用真实临时 xlsx + 真实图片占位文件。"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from camera_sync.copy_false import copy_false_images
from camera_sync.excel_writer import write_report


def test_copies_only_false_rows(tmp_path: Path):
    pytest.importorskip("openpyxl")

    src = tmp_path / "frames"
    dst = tmp_path / "false"
    src.mkdir()

    files = ["a.jpg", "b.jpg", "c.jpg"]
    for name in files:
        (src / name).write_bytes(b"\x00")

    results = {
        "a.jpg": ["00:01:02:03", "00:01:02:03"],   # True
        "b.jpg": ["00:01:02:03", "00:01:02:99"],   # False
        "c.jpg": [],                                # False
    }
    excel_dir = tmp_path / "report"
    excel_dir.mkdir()
    excel_path = write_report(
        results=results,
        excel_dir=excel_dir,
        prefix="Sync_n_Timecode",
        highlight_color="FFCCCC",
        now=datetime(2026, 5, 8, 0, 0, 0),
        insert_chart=False,
    )

    copied, missing = copy_false_images(excel_path, src, dst)
    assert copied == 2
    assert missing == 0
    assert (dst / "b.jpg").exists()
    assert (dst / "c.jpg").exists()
    assert not (dst / "a.jpg").exists()


def test_logs_missing_source(tmp_path: Path, caplog):
    pytest.importorskip("openpyxl")

    src = tmp_path / "frames"
    dst = tmp_path / "false"
    src.mkdir()
    # 仅放 a.jpg；b.jpg 在 Excel 中是 False 但磁盘缺失
    (src / "a.jpg").write_bytes(b"x")

    results = {
        "a.jpg": ["x", "y"],   # False
        "b.jpg": ["x", "y"],   # False，但物理文件缺失
    }
    excel_dir = tmp_path / "report"
    excel_dir.mkdir()
    excel_path = write_report(
        results=results,
        excel_dir=excel_dir,
        prefix="Sync_n_Timecode",
        highlight_color="FFCCCC",
        now=datetime(2026, 5, 8, 0, 0, 0),
        insert_chart=False,
    )
    caplog.clear()
    copied, missing = copy_false_images(excel_path, src, dst)
    assert copied == 1 and missing == 1
    assert any("File not found" in r.message for r in caplog.records)


def test_skips_summary_row_explicitly(tmp_path: Path):
    """即使有人把 Summary 行的 IsSame 写成空字符串，也不应触发复制。"""
    pytest.importorskip("openpyxl")
    src = tmp_path / "frames"
    dst = tmp_path / "false"
    src.mkdir()
    (src / "a.jpg").write_bytes(b"x")

    excel_dir = tmp_path / "report"
    excel_dir.mkdir()
    excel_path = write_report(
        results={"a.jpg": ["x", "x"]},
        excel_dir=excel_dir,
        prefix="Sync_n_Timecode",
        highlight_color="FFCCCC",
        now=datetime(2026, 5, 8, 0, 0, 0),
        insert_chart=False,
    )

    copied, missing = copy_false_images(excel_path, src, dst)
    assert copied == 0 and missing == 0
    assert list(dst.iterdir()) == []
