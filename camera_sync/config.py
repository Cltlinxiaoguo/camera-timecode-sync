# -*- coding: utf-8 -*-
"""配置加载与校验。

设计要点：
1. 配置文件与可执行文件同目录，名为 ``camera_sync_config.yaml``。
2. 缺失时自动写出"内置默认模板"（见 ``DEFAULT_CONFIG_TEMPLATE``）。
3. 所有路径支持相对路径，以配置文件所在目录为基准解析为绝对路径。
4. 类型与必填项校验后返回不可变 dataclass，避免散落 dict 在业务层。
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml


CONFIG_FILENAME = "camera_sync_config.yaml"


@dataclass(frozen=True)
class PathsConfig:
    cr2_dir: Path
    jpg_dir: Path
    false_dir: Path
    excel_dir: Path
    log_dir: Path


@dataclass(frozen=True)
class CropConfig:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class OcrConfig:
    lang: str
    use_gpu: bool
    timecode_regex: str
    force_hour_zero: bool


@dataclass(frozen=True)
class RuntimeConfig:
    max_workers: int  # 0 = auto
    fail_fast_on_ocr_error: bool


@dataclass(frozen=True)
class ExcelConfig:
    filename_prefix: str
    highlight_color: str  # 6 位十六进制，无 #


@dataclass(frozen=True)
class PipelineConfig:
    do_clear_jpg_dir: bool
    do_cr2_to_jpg: bool
    do_ocr_report: bool
    do_clear_false_dir: bool
    do_copy_false: bool


@dataclass(frozen=True)
class UiConfig:
    pause_before_exit: bool


@dataclass(frozen=True)
class AppConfig:
    paths: PathsConfig
    crop: CropConfig
    ocr: OcrConfig
    runtime: RuntimeConfig
    excel: ExcelConfig
    pipeline: PipelineConfig
    ui: UiConfig
    config_path: Path  # 解析时使用的实际 YAML 路径


# ---------------------------------------------------------------------------
# 默认模板（与 camera_sync_config.yaml 同步；缺失时由本程序写出）
# ---------------------------------------------------------------------------
DEFAULT_CONFIG_TEMPLATE: str = """# 相机同步检测工具 配置文件（由程序自动生成的默认模板）
# 详细注释参见仓库根目录 camera_sync_config.yaml。
paths:
  cr2_dir: 'C:\\path\\to\\cr2'
  jpg_dir: 'C:\\path\\to\\frames'
  false_dir: 'C:\\path\\to\\false'
  excel_dir: 'C:\\path\\to\\reports'
  log_dir: 'C:\\path\\to\\logs'
crop:
  x: 740
  y: 2240
  width: 1621
  height: 1428
ocr:
  lang: 'ch'
  use_gpu: false
  timecode_regex: '\\\\d{2}:\\\\d{2}:\\\\d{2}:\\\\d{2}'
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
  pause_before_exit: true
"""


class ConfigError(Exception):
    """配置文件相关错误的统一类型。"""


# ---------------------------------------------------------------------------
# 解析函数
# ---------------------------------------------------------------------------
def _resolve_path(base_dir: Path, value: str, default_subdir: Optional[str] = None) -> Path:
    """把字符串路径解析为绝对 Path；空字符串使用 ``default_subdir``。"""
    if value is None or str(value).strip() == "":
        if default_subdir is None:
            raise ConfigError("路径必填，但配置中为空字符串")
        return (base_dir / default_subdir).resolve()
    p = Path(str(value)).expanduser()
    if not p.is_absolute():
        p = (base_dir / p).resolve()
    return p


def _require(d: dict, key: str, section: str) -> Any:
    if key not in d:
        raise ConfigError(f"配置 [{section}] 缺少字段: {key}")
    return d[key]


def _parse(raw: dict, base_dir: Path, config_path: Path) -> AppConfig:
    if not isinstance(raw, dict):
        raise ConfigError("YAML 顶层必须为字典")

    paths = _require(raw, "paths", "root")
    crop = _require(raw, "crop", "root")
    ocr = _require(raw, "ocr", "root")
    runtime = _require(raw, "runtime", "root")
    excel = _require(raw, "excel", "root")
    pipeline = _require(raw, "pipeline", "root")
    ui = _require(raw, "ui", "root")

    paths_cfg = PathsConfig(
        cr2_dir=_resolve_path(base_dir, _require(paths, "cr2_dir", "paths")),
        jpg_dir=_resolve_path(base_dir, _require(paths, "jpg_dir", "paths")),
        false_dir=_resolve_path(base_dir, _require(paths, "false_dir", "paths")),
        excel_dir=_resolve_path(base_dir, paths.get("excel_dir", ""), default_subdir="."),
        log_dir=_resolve_path(base_dir, paths.get("log_dir", ""), default_subdir="logs"),
    )

    crop_cfg = CropConfig(
        x=int(_require(crop, "x", "crop")),
        y=int(_require(crop, "y", "crop")),
        width=int(_require(crop, "width", "crop")),
        height=int(_require(crop, "height", "crop")),
    )
    if crop_cfg.width <= 0 or crop_cfg.height <= 0:
        raise ConfigError("crop.width / crop.height 必须为正整数")
    if crop_cfg.x < 0 or crop_cfg.y < 0:
        raise ConfigError("crop.x / crop.y 不能为负数")

    ocr_cfg = OcrConfig(
        lang=str(ocr.get("lang", "ch")),
        use_gpu=bool(ocr.get("use_gpu", False)),
        timecode_regex=str(_require(ocr, "timecode_regex", "ocr")),
        force_hour_zero=bool(ocr.get("force_hour_zero", True)),
    )

    runtime_cfg = RuntimeConfig(
        max_workers=int(runtime.get("max_workers", 0)),
        fail_fast_on_ocr_error=bool(runtime.get("fail_fast_on_ocr_error", False)),
    )

    excel_cfg = ExcelConfig(
        filename_prefix=str(excel.get("filename_prefix", "Sync_n_Timecode")),
        highlight_color=_normalize_color(str(excel.get("highlight_color", "FFCCCC"))),
    )

    pipeline_cfg = PipelineConfig(
        do_clear_jpg_dir=bool(pipeline.get("do_clear_jpg_dir", True)),
        do_cr2_to_jpg=bool(pipeline.get("do_cr2_to_jpg", True)),
        do_ocr_report=bool(pipeline.get("do_ocr_report", True)),
        do_clear_false_dir=bool(pipeline.get("do_clear_false_dir", True)),
        do_copy_false=bool(pipeline.get("do_copy_false", True)),
    )

    ui_cfg = UiConfig(
        pause_before_exit=bool(ui.get("pause_before_exit", True)),
    )

    return AppConfig(
        paths=paths_cfg,
        crop=crop_cfg,
        ocr=ocr_cfg,
        runtime=runtime_cfg,
        excel=excel_cfg,
        pipeline=pipeline_cfg,
        ui=ui_cfg,
        config_path=config_path,
    )


def _normalize_color(value: str) -> str:
    v = value.strip().lstrip("#").upper()
    if len(v) != 6 or any(c not in "0123456789ABCDEF" for c in v):
        raise ConfigError(f"excel.highlight_color 非法（应为 6 位十六进制 RGB，例如 FFCCCC）：{value}")
    return v


# ---------------------------------------------------------------------------
# 公共 API
# ---------------------------------------------------------------------------
def get_app_dir() -> Path:
    """获取程序所在目录（PyInstaller onefile 兼容）。

    PyInstaller onefile 时 ``sys.executable`` 是真实 exe 路径，
    临时解压目录在 ``sys._MEIPASS`` 中——配置应放在 exe 旁边而非临时目录。
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def default_config_path() -> Path:
    return get_app_dir() / CONFIG_FILENAME


def write_default_config(target: Path) -> Path:
    """把内置模板写到 ``target``，已存在则不覆盖；返回最终路径。"""
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_text(DEFAULT_CONFIG_TEMPLATE, encoding="utf-8")
    return target


def load_config(config_path: Optional[os.PathLike] = None) -> AppConfig:
    """加载并校验配置；缺失则写出默认模板后再加载。"""
    cfg_path = Path(config_path) if config_path else default_config_path()

    if not cfg_path.exists():
        write_default_config(cfg_path)

    try:
        with cfg_path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"YAML 解析失败 ({cfg_path}): {e}") from e

    base_dir = cfg_path.resolve().parent
    return _parse(raw, base_dir, cfg_path.resolve())
