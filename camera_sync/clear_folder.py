# -*- coding: utf-8 -*-
"""清空目录但保留目录本身（等价 Clear_folder.py 的 clear_folder_contents）。

异常按 PRD 要求捕获并通过 logger 记录，不再直接 print。
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Union

from .logging_setup import get_logger


PathLike = Union[str, os.PathLike]


def clear_folder_contents(folder_path: PathLike, ensure_exists: bool = True) -> int:
    """清除目录内容，目录本身保留。

    Args:
        folder_path: 目标目录。
        ensure_exists: 若目录不存在是否创建（True，创建后内容必为空）。

    Returns:
        实际删除的条目数（文件 + 子目录计数）。
    """
    log = get_logger(__name__)
    folder = Path(folder_path)

    if not folder.exists():
        if ensure_exists:
            folder.mkdir(parents=True, exist_ok=True)
            log.info("目录不存在已创建: %s", folder)
            return 0
        log.warning("目录不存在且不创建，跳过清空: %s", folder)
        return 0

    if not folder.is_dir():
        raise NotADirectoryError(f"路径存在但不是目录: {folder}")

    deleted = 0
    for entry in folder.iterdir():
        try:
            if entry.is_file() or entry.is_symlink():
                entry.unlink()
                deleted += 1
            elif entry.is_dir():
                shutil.rmtree(entry)
                deleted += 1
        except Exception as e:
            log.error("删除失败 %s: %s", entry, e)
    log.info("已清空 %s（删除 %d 项）", folder, deleted)
    return deleted
