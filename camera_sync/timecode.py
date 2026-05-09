# -*- coding: utf-8 -*-
"""时间码处理纯函数：可独立单测，不依赖 PaddleOCR / cv2 / pandas。

来源：CS8K_n_Timecode.py 中的正则匹配 + 首段强制归零 + 同步判定逻辑。
"""
from __future__ import annotations

import re
from typing import Iterable, List, Sequence


def extract_timecodes(ocr_lines: Iterable, regex_pattern: str) -> List[str]:
    """从 PaddleOCR 一次 ocr() 的返回结构里提取符合正则的时间码字符串。

    PaddleOCR 返回结构：``result[0]`` 为本张图的多行结果，每个元素形如
    ``[box, (text, score)]``。本函数兼容 ``[box, (text, score)]`` 与
    ``(box, (text, score))`` 两种形态，且会跳过空文本。
    """
    pattern = re.compile(regex_pattern)
    out: List[str] = []
    for line in ocr_lines or []:
        # line 形如 [box, (text, score)] 或 (box, (text, score))
        if not line or len(line) < 2:
            continue
        info = line[1]
        if not info:
            continue
        text = info[0] if isinstance(info, (list, tuple)) else info
        if not isinstance(text, str):
            continue
        if pattern.fullmatch(text):
            out.append(text)
    return out


def force_hour_zero(timecodes: Sequence[str]) -> List[str]:
    """把 ``HH:MM:SS:FF`` 形式的首段（小时位）强制设为 ``00``。

    与原脚本完全一致：仅当冒号分割结果恰好为 4 段时才覆盖，其余原样保留。
    """
    out: List[str] = []
    for ts in timecodes:
        parts = ts.split(":")
        if len(parts) == 4:
            parts[0] = "00"
            out.append(":".join(parts))
        else:
            out.append(ts)
    return out


def is_same_timecodes(timecodes: Sequence[str]) -> bool:
    """所有时间码完全一致且非空时返回 True。

    保持与原脚本判定一致：
        len(set(timecodes)) == 1 and bool(timecodes)
    """
    return len(set(timecodes)) == 1 and bool(timecodes)
