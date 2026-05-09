# -*- coding: utf-8 -*-
"""OCR 工作进程：每个 worker 仅初始化一次 PaddleOCR。

PRD 性能要求：
    多进程执行 OCR 时，避免 Windows 下 PaddleOCR 在每个子进程重复全量初始化
    带来的冗余。

实现方式：
    ProcessPoolExecutor(initializer=_init_worker, initargs=(...))
    在子进程模块级缓存 PaddleOCR 实例，多次任务复用同一实例。
"""
from __future__ import annotations

import logging
import os
from typing import List, Optional, Tuple

from .timecode import extract_timecodes, force_hour_zero, is_same_timecodes


# --- 子进程级单例缓存 -------------------------------------------------------
_OCR_INSTANCE = None          # type: ignore[var-annotated]
_OCR_LANG: Optional[str] = None
_OCR_REGEX: Optional[str] = None
_OCR_FORCE_HOUR_ZERO: bool = True


def _init_worker(lang: str, use_gpu: bool, regex: str, force_hour_zero_flag: bool) -> None:
    """ProcessPoolExecutor initializer。子进程启动时跑一次。"""
    global _OCR_INSTANCE, _OCR_LANG, _OCR_REGEX, _OCR_FORCE_HOUR_ZERO

    logging.getLogger("ppocr").setLevel(logging.ERROR)

    from paddleocr import PaddleOCR
    kwargs = {"lang": lang}
    if use_gpu:
        kwargs["use_gpu"] = True
    _OCR_INSTANCE = PaddleOCR(**kwargs)

    _OCR_LANG = lang
    _OCR_REGEX = regex
    _OCR_FORCE_HOUR_ZERO = bool(force_hour_zero_flag)


def _ensure_initialized(lang: str, use_gpu: bool, regex: str, force_hour_zero_flag: bool) -> None:
    """主进程直接调用 ``process_image`` 时（如未来单测）也能完成初始化。"""
    global _OCR_INSTANCE
    if _OCR_INSTANCE is None:
        _init_worker(lang, use_gpu, regex, force_hour_zero_flag)


def _imread_unicode_safe(path: str):
    """cv2.imread 在 Windows + 含中文路径时会静默失败（返回 None）。

    使用 ``np.fromfile`` + ``cv2.imdecode`` 绕过 OpenCV 自身的 ASCII 路径假设。
    返回 BGR ndarray；失败时返回 None。
    """
    import cv2
    import numpy as np
    try:
        data = np.fromfile(path, dtype=np.uint8)
        if data.size == 0:
            return None
        return cv2.imdecode(data, cv2.IMREAD_COLOR)
    except Exception:
        return None


def _raw_ocr_texts(ocr_lines) -> List[str]:
    """从 PaddleOCR 单页结果里提取所有识别文本，用于失败诊断回显。"""
    out: List[str] = []
    for line in ocr_lines or []:
        try:
            text = line[1][0]
            if isinstance(text, str):
                out.append(text)
        except Exception:
            continue
    return out


def process_image(
    img_path: str,
    *,
    lang: str = "ch",
    use_gpu: bool = False,
    regex: str = r"\d{2}:\d{2}:\d{2}:\d{2}",
    force_hour_zero_flag: bool = True,
) -> Tuple[str, List[str]]:
    """处理单张 JPG，返回 (img_path, 校正后的时间码列表)。

    异常会被记录但不抛出（与原脚本行为一致：返回空列表 + 打印日志），
    上层根据 ``runtime.fail_fast_on_ocr_error`` 决定是否中止。

    诊断增强：当过滤后时间码为空（[NG]）时，会把 PaddleOCR 实际识别到的全部
    原始文本一并打到 WARNING 级日志，便于现场判断是裁剪丢了 OSD 还是格式不匹配。
    """
    _ensure_initialized(lang, use_gpu, regex, force_hour_zero_flag)
    assert _OCR_INSTANCE is not None and _OCR_REGEX is not None

    log = logging.getLogger("camera_sync.ocr")

    try:
        image = _imread_unicode_safe(img_path)
        if image is None:
            raise IOError(
                f"读取图像失败（文件不存在 / 损坏 / 路径有问题）: {img_path}"
            )

        result = _OCR_INSTANCE.ocr(image)
        ocr_lines = result[0] if result else []

        timecodes = extract_timecodes(ocr_lines, _OCR_REGEX)
        if _OCR_FORCE_HOUR_ZERO:
            timecodes = force_hour_zero(timecodes)

        is_same = is_same_timecodes(timecodes)
        # 与历史控制台 / 用户参考图一致的逐张输出（整段一条 INFO，GUI 与文件同显）。
        # 额外几行 str 的日志开销相对 OCR 可忽略，不影响总耗时。
        status = "[✅]" if is_same else "[❌]"
        msg = (
            "-----------------------------------\n"
            f"{os.path.basename(img_path)}\n"
            f"{timecodes}\n"
            f"{status}"
        )
        log.info(msg)

        # 诊断回显：识别失败 / 没拿到时间码时，把原始 OCR 全部文本贴出来
        if not timecodes:
            raw = _raw_ocr_texts(ocr_lines)
            if raw:
                log.warning(
                    "[诊断] %s 未匹配到时间码；OCR 实际识别到的文本: %s",
                    os.path.basename(img_path), raw,
                )
            else:
                log.warning(
                    "[诊断] %s 未识别到任何文本；裁剪区可能丢失 OSD，"
                    "或图像过暗/模糊/分辨率过低",
                    os.path.basename(img_path),
                )

        return img_path, timecodes
    except Exception as e:
        log.error(
            "-----------------------------------\nError processing image %s: %s",
            img_path,
            e,
        )
        return img_path, []


def diagnose_image(
    img_path: str,
    *,
    lang: str = "ch",
    use_gpu: bool = False,
    regex: str = r"\d{2}:\d{2}:\d{2}:\d{2}",
    crop: "Optional[tuple[int, int, int, int]]" = None,
) -> dict:
    """单图诊断：返回 {"ok", "image_size", "raw_texts", "matched"}，供 GUI/CLI 使用。

    - ``ok=False`` 表示读图失败（中文路径问题、文件损坏等）；
    - ``raw_texts`` 是 OCR 实际识别到的全部文本（不过滤）；
    - ``matched`` 是经过 ``regex.fullmatch`` 过滤后的时间码列表；
    - ``crop=(x,y,w,h)`` 时使用裁剪后的图像跑 OCR。
    """
    import cv2

    _ensure_initialized(lang, use_gpu, regex, True)
    assert _OCR_INSTANCE is not None

    image = _imread_unicode_safe(img_path)
    if image is None:
        return {"ok": False, "image_size": None, "raw_texts": [], "matched": [], "error": f"读图失败: {img_path}"}

    if crop is not None:
        x, y, w, h = crop
        h_img, w_img = image.shape[:2]
        x2 = min(w_img, x + w)
        y2 = min(h_img, y + h)
        if x < w_img and y < h_img and x2 > x and y2 > y:
            image = image[y:y2, x:x2]

    result = _OCR_INSTANCE.ocr(image)
    ocr_lines = result[0] if result else []
    raw_texts = _raw_ocr_texts(ocr_lines)
    matched = extract_timecodes(ocr_lines, regex)
    return {
        "ok": True,
        "image_size": (image.shape[1], image.shape[0]),
        "raw_texts": raw_texts,
        "matched": matched,
    }
