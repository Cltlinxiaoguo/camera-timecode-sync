# -*- coding: utf-8 -*-
"""根据 Excel 中 Is Same==False 的行，把对应 JPG 复制到归档目录。

重构自 ``Copy_False.py``：
- excel_path 由主流程动态传入（不再硬编码带时间戳路径）；
- 源/目标目录走配置；
- 每一行打印明确日志（成功 / 不存在）。
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Tuple

import pandas as pd

from .excel_writer import COLUMN_FILENAME, COLUMN_ISSAME, SUMMARY_LABEL
from .logging_setup import get_logger


def copy_false_images(
    excel_path: Path,
    source_dir: Path,
    destination_dir: Path,
    sheet_name: str | int = 0,
) -> Tuple[int, int]:
    """读取 Excel，将 Is Same==False 的图片从 source 复制到 destination。

    Returns:
        (复制成功数, 源不存在数)
    """
    log = get_logger(__name__)
    excel_path = Path(excel_path)
    source_dir = Path(source_dir)
    destination_dir = Path(destination_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_excel(excel_path, sheet_name=sheet_name)
    log.info("Columns in the Excel file:")
    log.info("%s", df.columns.tolist())

    if COLUMN_FILENAME not in df.columns or COLUMN_ISSAME not in df.columns:
        raise ValueError(
            f"Excel 缺少必要列 {COLUMN_FILENAME!r} / {COLUMN_ISSAME!r}: 实际列={df.columns.tolist()}"
        )

    copied = 0
    missing = 0
    for _, row in df.iterrows():
        filename = row[COLUMN_FILENAME]
        if filename == SUMMARY_LABEL:
            continue
        is_same = row[COLUMN_ISSAME]
        # 与原脚本一致：if not row[is_same_col]
        # 但显式跳过空字符串（Summary 行已在上面 continue 兜底）
        if is_same is True or is_same == 1 or is_same == "True":
            continue
        if isinstance(is_same, str) and is_same.strip() == "":
            continue

        source_file = source_dir / str(filename)
        destination_file = destination_dir / str(filename)

        if source_file.exists():
            shutil.copy2(source_file, destination_file)
            log.info("Copied: %s", filename)
            copied += 1
        else:
            log.warning("File not found: %s", filename)
            missing += 1

    log.info("Operation completed.")
    return copied, missing
