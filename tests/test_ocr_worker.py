# -*- coding: utf-8 -*-
"""ocr_worker 中文路径安全 + 失败诊断 测试。

不依赖真实 PaddleOCR 模型；通过 monkeypatch 注入假 OCR 实例。
"""
from __future__ import annotations

from pathlib import Path

import pytest


def test_imread_unicode_safe_handles_chinese_path(tmp_path: Path):
    """中文路径下 cv2.imread 会返回 None；我们的 safe 版本必须能读到内容。"""
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    from camera_sync.ocr_worker import _imread_unicode_safe

    chinese_dir = tmp_path / "中文目录"
    chinese_dir.mkdir()
    img_path = chinese_dir / "测试图片.jpg"

    # 用 cv2.imencode 写一张纯白 JPG
    arr = np.full((20, 30, 3), 255, dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", arr)
    assert ok
    img_path.write_bytes(buf.tobytes())

    # baseline: 验证 cv2.imread 在中文路径上确实失败
    direct = cv2.imread(str(img_path))
    assert direct is None, "本测试假设 cv2.imread 在中文路径下返回 None"

    # 我们的 safe 版本必须读到 (h=20, w=30, 3)
    img = _imread_unicode_safe(str(img_path))
    assert img is not None
    assert img.shape == (20, 30, 3)


def test_imread_unicode_safe_returns_none_for_missing(tmp_path: Path):
    pytest.importorskip("cv2")
    from camera_sync.ocr_worker import _imread_unicode_safe
    assert _imread_unicode_safe(str(tmp_path / "does_not_exist.jpg")) is None


def test_raw_ocr_texts_extracts_all_strings():
    from camera_sync.ocr_worker import _raw_ocr_texts
    lines = [
        [[[0, 0]], ("hello", 0.9)],
        [[[0, 0]], ("01:23:45:67", 0.99)],
        None,                                   # 残缺
        [[[0, 0]], (None, 0.9)],                # 文本为 None
    ]
    assert _raw_ocr_texts(lines) == ["hello", "01:23:45:67"]


class _FakeOCR:
    def __init__(self, lines):
        self.lines = lines
    def ocr(self, _img):
        return [self.lines]


def test_process_image_warns_on_unmatched_raw_texts(monkeypatch, tmp_path: Path, caplog):
    """OCR 拿到文本但不匹配正则时，必须把原始文本回显到 WARNING。"""
    pytest.importorskip("cv2")
    pytest.importorskip("numpy")

    import camera_sync.ocr_worker as ow

    img_path = tmp_path / "t.jpg"
    img_path.write_bytes(b"x")  # 内容随便；imread 会被 mock

    monkeypatch.setattr(ow, "_imread_unicode_safe", lambda _p: object())  # 非 None 即可
    fake = _FakeOCR([
        [[[0, 0]], ("Hello World", 0.99)],
        [[[0, 0]], ("01-23-45-67", 0.95)],   # 不匹配 \d{2}:\d{2}:\d{2}:\d{2}
    ])
    monkeypatch.setattr(ow, "_OCR_INSTANCE", fake)
    monkeypatch.setattr(ow, "_OCR_REGEX", r"\d{2}:\d{2}:\d{2}:\d{2}")
    monkeypatch.setattr(ow, "_OCR_FORCE_HOUR_ZERO", True)

    caplog.set_level("WARNING", logger="camera_sync.ocr")
    _, codes = ow.process_image(str(img_path))
    assert codes == []
    msgs = [r.getMessage() for r in caplog.records]
    assert any("未匹配到时间码" in m and "Hello World" in m and "01-23-45-67" in m for m in msgs)


def test_process_image_warns_on_no_text(monkeypatch, tmp_path: Path, caplog):
    """OCR 没识别到任何文本时也要给出明确诊断。"""
    pytest.importorskip("cv2")

    import camera_sync.ocr_worker as ow

    img_path = tmp_path / "t.jpg"
    img_path.write_bytes(b"x")

    monkeypatch.setattr(ow, "_imread_unicode_safe", lambda _p: object())
    monkeypatch.setattr(ow, "_OCR_INSTANCE", _FakeOCR([]))
    monkeypatch.setattr(ow, "_OCR_REGEX", r"\d{2}:\d{2}:\d{2}:\d{2}")
    monkeypatch.setattr(ow, "_OCR_FORCE_HOUR_ZERO", True)

    caplog.set_level("WARNING", logger="camera_sync.ocr")
    ow.process_image(str(img_path))
    msgs = [r.getMessage() for r in caplog.records]
    assert any("未识别到任何文本" in m for m in msgs)


def test_process_image_no_warning_when_matched(monkeypatch, tmp_path: Path, caplog):
    """正常匹配时不应触发诊断 warning，避免日志噪音。"""
    pytest.importorskip("cv2")

    import camera_sync.ocr_worker as ow

    img_path = tmp_path / "t.jpg"
    img_path.write_bytes(b"x")

    monkeypatch.setattr(ow, "_imread_unicode_safe", lambda _p: object())
    monkeypatch.setattr(
        ow,
        "_OCR_INSTANCE",
        _FakeOCR([
            [[[0, 0]], ("01:23:45:67", 0.99)],
            [[[0, 0]], ("01:23:45:67", 0.98)],
        ]),
    )
    monkeypatch.setattr(ow, "_OCR_REGEX", r"\d{2}:\d{2}:\d{2}:\d{2}")
    monkeypatch.setattr(ow, "_OCR_FORCE_HOUR_ZERO", True)

    caplog.set_level("WARNING", logger="camera_sync.ocr")
    _, codes = ow.process_image(str(img_path))
    assert codes == ["00:23:45:67", "00:23:45:67"]   # force_hour_zero 生效
    diagnostic_msgs = [r for r in caplog.records if "诊断" in r.getMessage()]
    assert diagnostic_msgs == [], "正常匹配不应有诊断日志"


def test_diagnose_image_returns_structure(monkeypatch, tmp_path: Path):
    """diagnose_image() 返回 dict 包含 ok/image_size/raw_texts/matched。"""
    pytest.importorskip("cv2")
    pytest.importorskip("numpy")
    import numpy as np

    import camera_sync.ocr_worker as ow

    img_path = tmp_path / "t.jpg"
    img_path.write_bytes(b"x")

    fake_image = np.zeros((100, 200, 3), dtype=np.uint8)
    monkeypatch.setattr(ow, "_imread_unicode_safe", lambda _p: fake_image)
    monkeypatch.setattr(
        ow,
        "_OCR_INSTANCE",
        _FakeOCR([
            [[[0, 0]], ("hello", 0.9)],
            [[[0, 0]], ("01:23:45:67", 0.99)],
        ]),
    )

    out = ow.diagnose_image(str(img_path), regex=r"\d{2}:\d{2}:\d{2}:\d{2}")
    assert out["ok"] is True
    assert out["image_size"] == (200, 100)
    assert "hello" in out["raw_texts"] and "01:23:45:67" in out["raw_texts"]
    assert out["matched"] == ["01:23:45:67"]


def test_diagnose_image_handles_unread_file(monkeypatch, tmp_path: Path):
    pytest.importorskip("cv2")
    import camera_sync.ocr_worker as ow

    img_path = tmp_path / "broken.jpg"
    img_path.write_bytes(b"x")
    monkeypatch.setattr(ow, "_imread_unicode_safe", lambda _p: None)

    out = ow.diagnose_image(str(img_path))
    assert out["ok"] is False
    assert out["raw_texts"] == [] and out["matched"] == []
