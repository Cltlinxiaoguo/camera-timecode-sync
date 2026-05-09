# -*- coding: utf-8 -*-
"""Clear_folder 行为测试。"""
from __future__ import annotations

from pathlib import Path

import pytest

from camera_sync.clear_folder import clear_folder_contents


def test_clears_files_keeps_folder(tmp_path: Path):
    (tmp_path / "a.txt").write_text("x")
    (tmp_path / "b.bin").write_bytes(b"\x00\x01")
    deleted = clear_folder_contents(tmp_path)
    assert deleted == 2
    assert tmp_path.exists()
    assert list(tmp_path.iterdir()) == []


def test_clears_subdirectories(tmp_path: Path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "x.txt").write_text("y")
    (tmp_path / "z.txt").write_text("z")
    deleted = clear_folder_contents(tmp_path)
    assert deleted == 2
    assert tmp_path.exists()
    assert list(tmp_path.iterdir()) == []


def test_creates_missing_when_ensure_exists(tmp_path: Path):
    target = tmp_path / "missing"
    deleted = clear_folder_contents(target, ensure_exists=True)
    assert deleted == 0
    assert target.exists() and target.is_dir()


def test_skips_when_missing_and_not_ensure(tmp_path: Path):
    target = tmp_path / "still_missing"
    deleted = clear_folder_contents(target, ensure_exists=False)
    assert deleted == 0
    assert not target.exists()


def test_raises_when_path_is_a_file(tmp_path: Path):
    f = tmp_path / "file.txt"
    f.write_text("x")
    with pytest.raises(NotADirectoryError):
        clear_folder_contents(f)
