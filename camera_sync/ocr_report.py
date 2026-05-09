# -*- coding: utf-8 -*-
"""OCR 流水线：列举 JPG → 多进程 OCR → 汇总 → 写 Excel。"""
from __future__ import annotations

import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .config import AppConfig
from .excel_writer import write_report
from .logging_setup import get_logger
from .ocr_worker import _init_worker, process_image


def _list_jpg(folder: Path) -> List[Path]:
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".jpg")


def _is_frozen() -> bool:
    """是否运行在 PyInstaller / 冻结发行包中。"""
    return bool(getattr(sys, "frozen", False))


def _resolve_max_workers(configured: int, image_count: int) -> Tuple[int, str]:
    """决定本次实际使用的 worker 数 + 解释原因。

    Returns:
        (workers, reason)

    规则：
    1. **冻结模式（PyInstaller onefile + Windows）下强制单进程**——
       这是已知的 PaddleOCR + multiprocessing.spawn + PyInstaller 三向不兼容问题：
       子进程在重新引导冻结运行时时初始化 paddle C 扩展会"猝死"，错误形如
       "A process in the process pool was terminated abruptly"。
       PRD P2/P4 优先稳定性而非速度——4-200 张典型场景单进程已足够。
    2. configured <= 0 → 自动取 min(8, cpu_count())。
    3. configured > 0  → 取该值，但不超过 cpu_count()。
    4. 任意模式下都不超过图片数（避免起 8 worker 处理 2 张图的浪费）。
    5. image_count == 0 时返回 1（兜底）。
    """
    cpu = os.cpu_count() or 1

    if _is_frozen():
        return 1, f"frozen=True，强制单进程（避免 PyInstaller + Paddle 子进程崩溃）"

    if configured <= 0:
        base = min(8, cpu)
        why = f"配置=0 自动取 min(8, cpu={cpu})={base}"
    else:
        base = min(configured, cpu)
        why = f"配置={configured}，受 cpu={cpu} 限制后={base}"

    if image_count == 0:
        return 1, why + "；图片数=0，回退为 1"
    if base > image_count:
        return image_count, why + f"；再受图片数={image_count} 限制"
    return max(1, base), why


def run_ocr_and_report(cfg: AppConfig) -> Optional[Path]:
    """对 ``cfg.paths.jpg_dir`` 下的 JPG 全部 OCR、构造 DataFrame、写 Excel。

    Returns:
        本次 Excel 报告绝对路径；若没有 JPG 则返回 None。
    """
    log = get_logger(__name__)
    jpg_dir = cfg.paths.jpg_dir

    if not jpg_dir.exists():
        log.error("JPG 目录不存在: %s", jpg_dir)
        return None

    images = _list_jpg(jpg_dir)
    if not images:
        log.error("JPG 目录中没有图片可识别: %s", jpg_dir)
        return None

    max_workers, reason = _resolve_max_workers(cfg.runtime.max_workers, len(images))
    log.info("开始处理 %d 张图像，使用 %d 个工作进程（原因：%s）", len(images), max_workers, reason)
    log.info(
        "逐张识别结果见下方分隔块（文件名 / 时间码列表 / 同步状态）；"
        "汇总统计在全部识别完成后输出。"
    )

    results: Dict[str, List[str]] = {}

    init_args = (
        cfg.ocr.lang,
        cfg.ocr.use_gpu,
        cfg.ocr.timecode_regex,
        cfg.ocr.force_hour_zero,
    )

    if max_workers <= 1:
        # 单进程模式：在主进程直接处理（便于调试与小批量任务），不构建进程池。
        _init_worker(*init_args)
        for img in images:
            try:
                _, time_strings = process_image(
                    str(img),
                    lang=cfg.ocr.lang,
                    use_gpu=cfg.ocr.use_gpu,
                    regex=cfg.ocr.timecode_regex,
                    force_hour_zero_flag=cfg.ocr.force_hour_zero,
                )
                results[img.name] = time_strings
            except Exception as e:
                log.error("Error encountered while handling future result for %s: %s", img, e)
                if cfg.runtime.fail_fast_on_ocr_error:
                    raise
                results[img.name] = []
    else:
        with ProcessPoolExecutor(
            max_workers=max_workers,
            initializer=_init_worker,
            initargs=init_args,
        ) as executor:
            futures_to_img = {
                executor.submit(
                    process_image,
                    str(img),
                    lang=cfg.ocr.lang,
                    use_gpu=cfg.ocr.use_gpu,
                    regex=cfg.ocr.timecode_regex,
                    force_hour_zero_flag=cfg.ocr.force_hour_zero,
                ): img
                for img in images
            }
            for future in as_completed(futures_to_img):
                img = futures_to_img[future]
                try:
                    _, time_strings = future.result()
                    results[img.name] = time_strings
                except Exception as e:
                    log.error("Error encountered while handling future result for %s: %s", img, e)
                    if cfg.runtime.fail_fast_on_ocr_error:
                        raise
                    results[img.name] = []

    excel_path = write_report(
        results=results,
        excel_dir=cfg.paths.excel_dir,
        prefix=cfg.excel.filename_prefix,
        highlight_color=cfg.excel.highlight_color,
    )
    return excel_path
