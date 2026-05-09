# -*- coding: utf-8 -*-
"""主流水线串联：clear → cr2_to_jpg → ocr_report → clear false → copy_false。"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from .clear_folder import clear_folder_contents
from .config import AppConfig, ConfigError, default_config_path, load_config
from .copy_false import copy_false_images
from .cr2_to_jpg import convert_folder
from .logging_setup import get_logger, setup_logging
from .ocr_report import run_ocr_and_report


def _format_elapsed(start: datetime) -> str:
    delta = datetime.now() - start
    return f"{delta.total_seconds():.2f} 秒"


def _sep(title: str = "") -> str:
    """与历史控制台 / 图二风格一致的横向分隔线。"""
    line = "-" * 52
    return f"{line}\n{title}".strip() if title else line


def run(config_path: Optional[os.PathLike] = None) -> int:
    """主流水线入口；返回进程退出码（0 = 成功，非 0 = 失败）。"""
    start_time = datetime.now()

    # 1. 加载配置 ----------------------------------------------------------
    cfg_path = Path(config_path) if config_path else default_config_path()
    try:
        cfg: AppConfig = load_config(cfg_path)
    except ConfigError as e:
        # 此时 logging 还未初始化，直接 stderr 输出
        sys.stderr.write(f"[配置错误] {e}\n")
        return 2

    # 2. 初始化日志 --------------------------------------------------------
    log_file = setup_logging(cfg.paths.log_dir)
    log = get_logger("camera_sync.pipeline")
    log.info("================ 相机同步检测工具 启动 ================")
    log.info("配置文件: %s", cfg.config_path)
    log.info("日志文件: %s", log_file)
    log.info("CR2  目录: %s", cfg.paths.cr2_dir)
    log.info("JPG  目录: %s", cfg.paths.jpg_dir)
    log.info("False目录: %s", cfg.paths.false_dir)
    log.info("Excel目录: %s", cfg.paths.excel_dir)
    log.info("程序开始时间: %s", start_time)
    log.info(_sep("【流程】以下为各步骤执行记录（与控制台版对齐）"))

    excel_path = None
    exit_code = 0
    try:
        # 3. 清空中间帧目录 -----------------------------------------------
        if cfg.pipeline.do_clear_jpg_dir:
            log.info(_sep("步骤 1/5：清空 JPG 中间目录"))
            n = clear_folder_contents(cfg.paths.jpg_dir, ensure_exists=True)
            log.info("步骤 1 完成：已处理中间目录，本次删除 %d 项。", n)
        else:
            log.info("步骤 1/5：清空 JPG 中间目录 — 已跳过（pipeline.do_clear_jpg_dir=false）")

        # 4. CR2 → JPG -----------------------------------------------------
        if cfg.pipeline.do_cr2_to_jpg:
            log.info(_sep("步骤 2/5：CR2 转 JPG（裁剪）"))
            ok, fail = convert_folder(cfg.paths.cr2_dir, cfg.paths.jpg_dir, cfg.crop)
            log.info("步骤 2 完成：转换结束（成功=%d，失败=%d）。", ok, fail)
            if ok == 0:
                log.error("没有任何 CR2 转换成功，终止流程。")
                exit_code = 3
                return exit_code
        else:
            log.info("步骤 2/5：CR2 转 JPG — 已跳过（pipeline.do_cr2_to_jpg=false）")

        # 5. OCR + Excel ---------------------------------------------------
        if cfg.pipeline.do_ocr_report:
            log.info(_sep("步骤 3/5：OCR 识别与时间码分析、生成 Excel"))
            excel_path = run_ocr_and_report(cfg)
            log.info("步骤 3 完成：Excel 报告路径 %s", excel_path or "(未生成)")
            if excel_path is None:
                log.error("未生成 Excel 报告（无输入图像或上游失败），终止后续步骤。")
                exit_code = 4
                return exit_code
        else:
            log.info("步骤 3/5：OCR / Excel — 已跳过（pipeline.do_ocr_report=false）")

        # 6. 清空异常归档目录 ---------------------------------------------
        if cfg.pipeline.do_clear_false_dir:
            log.info(_sep("步骤 4/5：清空异常归档目录"))
            n_false = clear_folder_contents(cfg.paths.false_dir, ensure_exists=True)
            log.info("步骤 4 完成：异常目录已清空，本次删除 %d 项。", n_false)
        else:
            log.info("步骤 4/5：清空异常归档 — 已跳过（pipeline.do_clear_false_dir=false）")

        # 7. 复制不同步图片 -----------------------------------------------
        if cfg.pipeline.do_copy_false:
            log.info(_sep("步骤 5/5：复制不同步样本到异常归档"))
            if excel_path is None:
                # 未跑 OCR 但要复制：尝试找最近一份 Excel
                latest = _find_latest_excel(cfg.paths.excel_dir, cfg.excel.filename_prefix)
                if latest is None:
                    log.error("未找到 Excel 报告，跳过复制步骤。")
                else:
                    excel_path = latest
            if excel_path is not None:
                copy_false_images(
                    excel_path=excel_path,
                    source_dir=cfg.paths.jpg_dir,
                    destination_dir=cfg.paths.false_dir,
                )
            log.info("步骤 5 完成：异常样本复制结束。")
        else:
            log.info("步骤 5/5：复制异常样本 — 已跳过（pipeline.do_copy_false=false）")
    except KeyboardInterrupt:
        log.warning("用户中断（Ctrl+C）。")
        exit_code = 130
    except Exception as e:
        log.exception("流水线异常终止: %s", e)
        exit_code = 1
    finally:
        end_time = datetime.now()
        log.info(_sep("【汇总】程序时间统计"))
        log.info("程序开始时间: %s", start_time)
        log.info("程序结束时间: %s", end_time)
        log.info("总耗时: %s", _format_elapsed(start_time))
        log.info("退出码: %d", exit_code)
        log.info(_sep())

        if cfg.ui.pause_before_exit:
            try:
                input("按回车键退出...")
            except (EOFError, KeyboardInterrupt):
                pass
    return exit_code


def _find_latest_excel(excel_dir: Path, prefix: str) -> Optional[Path]:
    if not excel_dir.exists():
        return None
    candidates = sorted(
        (p for p in excel_dir.iterdir() if p.is_file() and p.name.startswith(prefix) and p.suffix.lower() == ".xlsx"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None
