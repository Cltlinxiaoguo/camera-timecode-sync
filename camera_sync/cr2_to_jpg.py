# -*- coding: utf-8 -*-
"""CR2 批量裁剪并导出 JPG。

重构自 ``Cr2 Cut Into Jpg.py``：
- 路径与裁剪坐标全部走配置；
- 单文件失败不中断整体（按 PRD"健壮性"要求）；
- 输出 jpg 用 ``cv2.imencode`` 写出以兼容含中文的路径（原 ``imageio.imsave``
  在中文路径上偶发失败）。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Tuple

import numpy as np

from .config import CropConfig
from .logging_setup import get_logger


def _list_cr2_files(input_dir: Path) -> List[Path]:
    return sorted(p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() == ".cr2")


def _safe_imwrite_jpg(path: Path, rgb_image: "np.ndarray") -> None:
    """以 imageio 优先、cv2 兜底的方式写出 JPG，兼容中文路径。"""
    try:
        import imageio
        imageio.imsave(str(path), rgb_image)
        return
    except Exception:
        pass
    import cv2
    bgr = rgb_image[:, :, ::-1] if rgb_image.ndim == 3 else rgb_image
    ok, buf = cv2.imencode(".jpg", bgr)
    if not ok:
        raise IOError(f"cv2.imencode 写出失败: {path}")
    path.write_bytes(buf.tobytes())


def convert_one(cr2_path: Path, jpg_path: Path, crop: CropConfig) -> None:
    """转换并裁剪单张 CR2 → JPG（无异常吞咽，调用方决定如何处理）。"""
    import rawpy

    with rawpy.imread(str(cr2_path)) as raw:
        rgb_image = raw.postprocess()

    h, w = rgb_image.shape[:2]
    x2 = min(w, crop.x + crop.width)
    y2 = min(h, crop.y + crop.height)
    if crop.x >= w or crop.y >= h:
        raise ValueError(
            f"裁剪起点超出图像范围: image=({w}x{h}) crop=({crop.x},{crop.y},{crop.width},{crop.height})"
        )
    cropped = rgb_image[crop.y:y2, crop.x:x2]
    _safe_imwrite_jpg(jpg_path, cropped)


def convert_folder(cr2_dir: Path, jpg_dir: Path, crop: CropConfig) -> Tuple[int, int]:
    """遍历 ``cr2_dir`` 下所有 CR2，输出到 ``jpg_dir``。

    Returns:
        (成功数, 失败数)
    """
    log = get_logger(__name__)
    cr2_dir = Path(cr2_dir)
    jpg_dir = Path(jpg_dir)
    jpg_dir.mkdir(parents=True, exist_ok=True)

    if not cr2_dir.exists():
        log.error("CR2 输入目录不存在: %s", cr2_dir)
        return 0, 0

    files = _list_cr2_files(cr2_dir)
    if not files:
        log.warning("CR2 输入目录中没有 .cr2 文件: %s", cr2_dir)
        return 0, 0

    ok, fail = 0, 0
    for src in files:
        dst = jpg_dir / (src.stem + ".jpg")
        try:
            convert_one(src, dst, crop)
            log.info("Converted and cropped: %s -> %s", src, dst)
            ok += 1
        except Exception as e:
            log.error("CR2 转 JPG 失败 %s: %s", src, e)
            fail += 1
    log.info("CR2 转 JPG 完成: 成功=%d 失败=%d 共=%d", ok, fail, len(files))
    return ok, fail
