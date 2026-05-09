# -*- coding: utf-8 -*-
"""时间码处理纯函数测试。"""
from __future__ import annotations

from camera_sync.timecode import extract_timecodes, force_hour_zero, is_same_timecodes


REGEX = r"\d{2}:\d{2}:\d{2}:\d{2}"


def _ocr_line(text: str, score: float = 0.99):
    return [[[0, 0], [1, 0], [1, 1], [0, 1]], (text, score)]


class TestExtractTimecodes:
    def test_extracts_only_matching_strings(self):
        lines = [
            _ocr_line("01:02:03:04"),
            _ocr_line("hello"),
            _ocr_line("99:99:99:99"),
            _ocr_line("01:02:03"),
        ]
        assert extract_timecodes(lines, REGEX) == ["01:02:03:04", "99:99:99:99"]

    def test_handles_empty_input(self):
        assert extract_timecodes([], REGEX) == []
        assert extract_timecodes(None, REGEX) == []

    def test_skips_malformed_entries(self):
        lines = [
            None,
            [],
            [[[0, 0]], None],
            [[[0, 0]], ("01:02:03:04", 0.9)],
        ]
        assert extract_timecodes(lines, REGEX) == ["01:02:03:04"]

    def test_fullmatch_not_substring(self):
        lines = [_ocr_line("prefix 01:02:03:04 suffix")]
        assert extract_timecodes(lines, REGEX) == []


class TestForceHourZero:
    def test_overrides_first_segment(self):
        assert force_hour_zero(["12:34:56:78", "00:00:00:00"]) == ["00:34:56:78", "00:00:00:00"]

    def test_keeps_non_4_segment_strings_untouched(self):
        assert force_hour_zero(["12:34:56", "abc"]) == ["12:34:56", "abc"]

    def test_empty_list(self):
        assert force_hour_zero([]) == []


class TestIsSameTimecodes:
    def test_all_same(self):
        assert is_same_timecodes(["00:01:02:03", "00:01:02:03"]) is True

    def test_some_different(self):
        assert is_same_timecodes(["00:01:02:03", "00:01:02:04"]) is False

    def test_empty_returns_false(self):
        # 与原脚本 bool(corrected_time_strings) 保持一致：空 → False
        assert is_same_timecodes([]) is False

    def test_single_item_returns_true(self):
        assert is_same_timecodes(["00:01:02:03"]) is True
