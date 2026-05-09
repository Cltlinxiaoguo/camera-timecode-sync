# -*- coding: utf-8 -*-
"""ocr_report._resolve_max_workers 行为测试。

PRD P2/P4 要求"在稳定性与速度间平衡"——
冻结模式（PyInstaller onefile + Windows + PaddleOCR）下必须强制单进程，
避免子进程"猝死"（A process in the process pool was terminated abruptly）。
"""
from __future__ import annotations

import sys

import pytest

from camera_sync.ocr_report import _resolve_max_workers


class TestResolveMaxWorkers:
    def test_frozen_mode_forces_single_process(self, monkeypatch):
        """关键修复：sys.frozen=True 时无视配置，永远返回 1。"""
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        # 即使 configured=8、images=100，也强制 1
        n, reason = _resolve_max_workers(8, 100)
        assert n == 1
        assert "frozen" in reason.lower() or "冻结" in reason or "单进程" in reason

    def test_dev_mode_zero_uses_auto(self, monkeypatch):
        """非冻结：configured=0 自动取 min(8, cpu)。"""
        monkeypatch.setattr(sys, "frozen", False, raising=False)
        monkeypatch.setattr("camera_sync.ocr_report.os.cpu_count", lambda: 16)
        n, _ = _resolve_max_workers(0, 100)
        assert n == 8  # min(8, 16) 受 image_count 限制后还是 8

    def test_dev_mode_explicit_workers_capped_by_cpu(self, monkeypatch):
        """非冻结：configured > cpu 时被 cpu 截断。"""
        monkeypatch.setattr(sys, "frozen", False, raising=False)
        monkeypatch.setattr("camera_sync.ocr_report.os.cpu_count", lambda: 4)
        n, _ = _resolve_max_workers(16, 100)
        assert n == 4

    def test_dev_mode_capped_by_image_count(self, monkeypatch):
        """关键：worker 数不能超过待处理图片数（避免 8 worker 处理 2 张图）。"""
        monkeypatch.setattr(sys, "frozen", False, raising=False)
        monkeypatch.setattr("camera_sync.ocr_report.os.cpu_count", lambda: 16)
        n, reason = _resolve_max_workers(0, 2)
        assert n == 2
        assert "图片数" in reason

    def test_dev_mode_zero_images_returns_one(self, monkeypatch):
        monkeypatch.setattr(sys, "frozen", False, raising=False)
        monkeypatch.setattr("camera_sync.ocr_report.os.cpu_count", lambda: 8)
        n, _ = _resolve_max_workers(0, 0)
        assert n == 1

    def test_negative_configured_treated_as_auto(self, monkeypatch):
        monkeypatch.setattr(sys, "frozen", False, raising=False)
        monkeypatch.setattr("camera_sync.ocr_report.os.cpu_count", lambda: 8)
        n, _ = _resolve_max_workers(-3, 100)
        assert n == 8
