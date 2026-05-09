# -*- coding: utf-8 -*-
"""YAML 配置加载与校验测试。"""
from __future__ import annotations

from pathlib import Path

import pytest

from camera_sync.config import (
    AppConfig,
    ConfigError,
    DEFAULT_CONFIG_TEMPLATE,
    load_config,
    write_default_config,
)


def test_load_minimal_yaml_ok(minimal_yaml: Path):
    cfg: AppConfig = load_config(minimal_yaml)
    assert cfg.paths.cr2_dir.exists()
    assert cfg.crop.x == 10 and cfg.crop.width == 100
    assert cfg.ocr.lang == "ch"
    assert cfg.ocr.force_hour_zero is True
    assert cfg.runtime.max_workers == 0
    assert cfg.excel.filename_prefix == "Sync_n_Timecode"
    assert cfg.excel.highlight_color == "FFCCCC"
    assert cfg.ui.pause_before_exit is False


def test_missing_yaml_writes_default_template(tmp_path: Path):
    target = tmp_path / "camera_sync_config.yaml"
    assert not target.exists()
    cfg = load_config(target)  # 应自动写出模板再加载
    assert target.exists()
    assert isinstance(cfg, AppConfig)
    # 模板内容应可识别
    text = target.read_text(encoding="utf-8")
    assert "paths:" in text and "crop:" in text


def test_invalid_color_raises(tmp_workspace: Path):
    yaml_path = tmp_workspace / "bad.yaml"
    yaml_path.write_text(
        f"""
paths:
  cr2_dir: '{(tmp_workspace / 'cr2').as_posix()}'
  jpg_dir: '{(tmp_workspace / 'jpg').as_posix()}'
  false_dir: '{(tmp_workspace / 'false').as_posix()}'
  excel_dir: ''
  log_dir: ''
crop: {{x: 0, y: 0, width: 10, height: 10}}
ocr: {{lang: 'ch', use_gpu: false, timecode_regex: '\\d+', force_hour_zero: true}}
runtime: {{max_workers: 2, fail_fast_on_ocr_error: false}}
excel: {{filename_prefix: 'X', highlight_color: 'ZZZZZZ'}}
pipeline: {{do_clear_jpg_dir: true, do_cr2_to_jpg: true, do_ocr_report: true, do_clear_false_dir: true, do_copy_false: true}}
ui: {{pause_before_exit: false}}
""".strip(),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_config(yaml_path)


def test_invalid_crop_raises(tmp_workspace: Path):
    yaml_path = tmp_workspace / "bad_crop.yaml"
    yaml_path.write_text(
        f"""
paths:
  cr2_dir: '{(tmp_workspace / 'cr2').as_posix()}'
  jpg_dir: '{(tmp_workspace / 'jpg').as_posix()}'
  false_dir: '{(tmp_workspace / 'false').as_posix()}'
  excel_dir: ''
  log_dir: ''
crop: {{x: -1, y: 0, width: 10, height: 10}}
ocr: {{lang: 'ch', use_gpu: false, timecode_regex: '\\d+', force_hour_zero: true}}
runtime: {{max_workers: 2, fail_fast_on_ocr_error: false}}
excel: {{filename_prefix: 'X', highlight_color: 'FFCCCC'}}
pipeline: {{do_clear_jpg_dir: true, do_cr2_to_jpg: true, do_ocr_report: true, do_clear_false_dir: true, do_copy_false: true}}
ui: {{pause_before_exit: false}}
""".strip(),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_config(yaml_path)


def test_default_template_is_loadable(tmp_path: Path):
    target = tmp_path / "camera_sync_config.yaml"
    write_default_config(target)
    assert target.exists()
    cfg = load_config(target)
    assert cfg.crop.width == 1621
    assert cfg.crop.height == 1428


def test_default_template_string_has_required_sections():
    for key in ("paths:", "crop:", "ocr:", "runtime:", "excel:", "pipeline:", "ui:"):
        assert key in DEFAULT_CONFIG_TEMPLATE


def test_relative_paths_resolved_against_yaml_dir(tmp_workspace: Path):
    yaml_path = tmp_workspace / "rel.yaml"
    yaml_path.write_text(
        """
paths:
  cr2_dir: 'cr2'
  jpg_dir: 'jpg'
  false_dir: 'false'
  excel_dir: ''
  log_dir: ''
crop: {x: 0, y: 0, width: 10, height: 10}
ocr: {lang: 'ch', use_gpu: false, timecode_regex: '\\d+', force_hour_zero: true}
runtime: {max_workers: 2, fail_fast_on_ocr_error: false}
excel: {filename_prefix: 'X', highlight_color: 'FFCCCC'}
pipeline: {do_clear_jpg_dir: true, do_cr2_to_jpg: true, do_ocr_report: true, do_clear_false_dir: true, do_copy_false: true}
ui: {pause_before_exit: false}
""".strip(),
        encoding="utf-8",
    )
    cfg = load_config(yaml_path)
    assert cfg.paths.cr2_dir == (tmp_workspace / "cr2").resolve()
    # excel_dir / log_dir 留空时分别落到 yaml 同目录与 logs 子目录
    assert cfg.paths.excel_dir == tmp_workspace.resolve()
    assert cfg.paths.log_dir == (tmp_workspace / "logs").resolve()
