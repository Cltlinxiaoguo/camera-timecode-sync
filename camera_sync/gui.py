# -*- coding: utf-8 -*-
"""相机同步检测工具 — Tkinter GUI。

设计要点：
1. 启动时尝试加载同目录 ``camera_sync_config.yaml``，缺失则写出默认模板再读，把所有
   字段回填到界面控件。
2. 三个核心路径（CR2 / JPG / 异常归档）配 ``[浏览]`` 按钮，用 ``filedialog.askdirectory``
   打开 Windows 原生选择器。
3. 「开始检测」点击后：
   - 把当前界面值写入临时 YAML（不覆盖用户原配置；强制 ``ui.pause_before_exit=false``
     避免 GUI 模式下出现 ``input()`` 阻塞）；
   - 在工作线程中运行 ``camera_sync.pipeline.run(temp_yaml)``，主线程通过
     ``after(100, ...)`` 轮询日志队列把日志贴到滚动文本框；
   - 运行结束后弹出汇总，并允许直接「打开报告目录 / false 目录 / 日志文件」。
4. 「保存到 YAML」按钮把当前界面值持久化回 ``camera_sync_config.yaml``，下次启动复用。
"""
from __future__ import annotations

import logging
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

import yaml

from .config import (
    AppConfig,
    ConfigError,
    DEFAULT_CONFIG_TEMPLATE,
    default_config_path,
    load_config,
    write_default_config,
)


_LOG_FMT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"


# ---------------------------------------------------------------------------
# Logging → Queue handler
# ---------------------------------------------------------------------------
class _QueueHandler(logging.Handler):
    """把所有 logger 输出 push 到 ``queue.Queue``，由 GUI 线程消费。"""

    def __init__(self, q: "queue.Queue[str]") -> None:
        super().__init__()
        self.q = q
        self.setFormatter(logging.Formatter(_LOG_FMT, datefmt=_LOG_DATEFMT))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.q.put(self.format(record))
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 主窗口
# ---------------------------------------------------------------------------
class CameraSyncGUI:
    PADDING = 6

    def __init__(self, root: tk.Tk, config_path: Path) -> None:
        self.root = root
        self.config_path = Path(config_path)
        self._ensure_config_exists()

        # 当前内存中的配置；GUI 控件初值都从这里取
        self.cfg: AppConfig = load_config(self.config_path)

        self.log_queue: "queue.Queue[str]" = queue.Queue()
        self.worker: Optional[threading.Thread] = None
        self.last_excel_path: Optional[Path] = None
        self.last_log_path: Optional[Path] = None

        # 控件变量（StringVar / IntVar / BooleanVar）
        self.var_cr2 = tk.StringVar(value=str(self.cfg.paths.cr2_dir))
        self.var_jpg = tk.StringVar(value=str(self.cfg.paths.jpg_dir))
        self.var_false = tk.StringVar(value=str(self.cfg.paths.false_dir))
        self.var_excel = tk.StringVar(value=str(self.cfg.paths.excel_dir))
        self.var_log = tk.StringVar(value=str(self.cfg.paths.log_dir))

        self.var_crop_x = tk.IntVar(value=self.cfg.crop.x)
        self.var_crop_y = tk.IntVar(value=self.cfg.crop.y)
        self.var_crop_w = tk.IntVar(value=self.cfg.crop.width)
        self.var_crop_h = tk.IntVar(value=self.cfg.crop.height)

        self.var_lang = tk.StringVar(value=self.cfg.ocr.lang)
        self.var_force_zero = tk.BooleanVar(value=self.cfg.ocr.force_hour_zero)
        self.var_use_gpu = tk.BooleanVar(value=self.cfg.ocr.use_gpu)
        self.var_workers = tk.IntVar(value=self.cfg.runtime.max_workers)

        self.var_status = tk.StringVar(value="就绪")

        self._build_ui()
        self._install_log_handler()
        self._poll_log()

    # -------------------------------------------------------------------
    # 启动准备
    # -------------------------------------------------------------------
    def _ensure_config_exists(self) -> None:
        if not self.config_path.exists():
            write_default_config(self.config_path)

    def _install_log_handler(self) -> None:
        """挂 handler 抓 camera_sync 日志到 GUI Queue。

        注意：不能挂在 root —— paddle 会在 import 时把 root 级别拉到 WARNING
        （详见 logging_setup.py 的注释）。挂在 ``camera_sync`` 命名 logger 上
        且 ``propagate=False``，与文件/控制台 handler 同源。
        """
        cam_logger = logging.getLogger("camera_sync")
        cam_logger.setLevel(logging.INFO)
        cam_logger.propagate = False
        for h in list(cam_logger.handlers):
            if isinstance(h, _QueueHandler):
                cam_logger.removeHandler(h)
        cam_logger.addHandler(_QueueHandler(self.log_queue))
        logging.getLogger("ppocr").setLevel(logging.ERROR)
        logging.getLogger("matplotlib").setLevel(logging.WARNING)
        logging.getLogger("PIL").setLevel(logging.WARNING)

    # -------------------------------------------------------------------
    # 界面构建
    # -------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = self.root
        root.title("相机同步检测工具")
        root.geometry("960x680")
        root.minsize(720, 520)

        try:
            ttk.Style().theme_use("vista")
        except tk.TclError:
            pass

        outer = ttk.Frame(root, padding=self.PADDING)
        outer.pack(fill=tk.BOTH, expand=True)

        # ----- 路径区 -----
        path_frame = ttk.LabelFrame(outer, text="路径", padding=self.PADDING)
        path_frame.pack(fill=tk.X)

        self._row_path(path_frame, 0, "CR2 输入目录",   self.var_cr2,   browse=True)
        self._row_path(path_frame, 1, "JPG 中间目录",   self.var_jpg,   browse=True)
        self._row_path(path_frame, 2, "异常归档目录",   self.var_false, browse=True)
        self._row_path(path_frame, 3, "Excel 报告目录", self.var_excel, browse=True)
        self._row_path(path_frame, 4, "日志目录",       self.var_log,   browse=True)
        path_frame.columnconfigure(1, weight=1)

        # ----- 参数区 -----
        param_frame = ttk.LabelFrame(outer, text="参数", padding=self.PADDING)
        param_frame.pack(fill=tk.X, pady=(self.PADDING, 0))

        ttk.Label(param_frame, text="裁剪 X:").grid(row=0, column=0, sticky=tk.W)
        ttk.Spinbox(param_frame, from_=0, to=99999, textvariable=self.var_crop_x, width=8).grid(row=0, column=1, sticky=tk.W, padx=(0, 12))
        ttk.Label(param_frame, text="Y:").grid(row=0, column=2, sticky=tk.W)
        ttk.Spinbox(param_frame, from_=0, to=99999, textvariable=self.var_crop_y, width=8).grid(row=0, column=3, sticky=tk.W, padx=(0, 12))
        ttk.Label(param_frame, text="宽:").grid(row=0, column=4, sticky=tk.W)
        ttk.Spinbox(param_frame, from_=1, to=99999, textvariable=self.var_crop_w, width=8).grid(row=0, column=5, sticky=tk.W, padx=(0, 12))
        ttk.Label(param_frame, text="高:").grid(row=0, column=6, sticky=tk.W)
        ttk.Spinbox(param_frame, from_=1, to=99999, textvariable=self.var_crop_h, width=8).grid(row=0, column=7, sticky=tk.W, padx=(0, 12))

        ttk.Label(param_frame, text="OCR 语种:").grid(row=1, column=0, sticky=tk.W, pady=(self.PADDING, 0))
        ttk.Combobox(
            param_frame,
            textvariable=self.var_lang,
            values=("ch", "en"),
            width=6,
            state="readonly",
        ).grid(row=1, column=1, sticky=tk.W, pady=(self.PADDING, 0))

        ttk.Label(param_frame, text="并发数:").grid(row=1, column=2, sticky=tk.W, pady=(self.PADDING, 0))
        ttk.Spinbox(param_frame, from_=0, to=64, textvariable=self.var_workers, width=6).grid(row=1, column=3, sticky=tk.W, pady=(self.PADDING, 0))

        ttk.Checkbutton(param_frame, text="强制小时位归零", variable=self.var_force_zero).grid(
            row=1, column=4, columnspan=2, sticky=tk.W, padx=(12, 0), pady=(self.PADDING, 0)
        )
        ttk.Checkbutton(param_frame, text="使用 GPU", variable=self.var_use_gpu).grid(
            row=1, column=6, columnspan=2, sticky=tk.W, padx=(12, 0), pady=(self.PADDING, 0)
        )

        # ----- 按钮区 -----
        btn_frame = ttk.Frame(outer, padding=(0, self.PADDING))
        btn_frame.pack(fill=tk.X)

        self.btn_start = ttk.Button(btn_frame, text="开始检测", command=self._on_start)
        self.btn_start.pack(side=tk.LEFT)

        ttk.Button(btn_frame, text="保存到 YAML", command=self._on_save_yaml).pack(side=tk.LEFT, padx=(self.PADDING, 0))
        ttk.Button(btn_frame, text="清空日志", command=self._on_clear_log).pack(side=tk.LEFT, padx=(self.PADDING, 0))

        self.btn_diagnose = ttk.Button(btn_frame, text="单图诊断", command=self._on_diagnose)
        self.btn_diagnose.pack(side=tk.LEFT, padx=(self.PADDING, 0))

        self.btn_open_excel = ttk.Button(btn_frame, text="打开最近报告", command=self._on_open_excel, state=tk.DISABLED)
        self.btn_open_excel.pack(side=tk.LEFT, padx=(self.PADDING, 0))

        ttk.Button(btn_frame, text="打开 Excel 目录", command=lambda: self._open_path(self.var_excel.get())).pack(side=tk.LEFT, padx=(self.PADDING, 0))
        ttk.Button(btn_frame, text="打开异常归档", command=lambda: self._open_path(self.var_false.get())).pack(side=tk.LEFT, padx=(self.PADDING, 0))
        ttk.Button(btn_frame, text="打开日志目录", command=lambda: self._open_path(self.var_log.get())).pack(side=tk.LEFT, padx=(self.PADDING, 0))

        # ----- 日志区 -----
        log_frame = ttk.LabelFrame(outer, text="日志", padding=self.PADDING)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(self.PADDING, 0))

        self.log_widget = tk.Text(
            log_frame,
            wrap=tk.NONE,
            state=tk.DISABLED,
            background="#111",
            foreground="#EEE",
            insertbackground="#EEE",
            font=("Consolas", 10),
        )
        yscroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_widget.yview)
        xscroll = ttk.Scrollbar(log_frame, orient=tk.HORIZONTAL, command=self.log_widget.xview)
        self.log_widget.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.log_widget.grid(row=0, column=0, sticky=tk.NSEW)
        yscroll.grid(row=0, column=1, sticky=tk.NS)
        xscroll.grid(row=1, column=0, sticky=tk.EW)
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        # 日志高亮 tag
        self.log_widget.tag_config("err", foreground="#FF6B6B")
        self.log_widget.tag_config("warn", foreground="#FFD166")
        self.log_widget.tag_config("ok", foreground="#90EE90")

        # ----- 状态栏 -----
        status_bar = ttk.Frame(outer)
        status_bar.pack(fill=tk.X, pady=(self.PADDING, 0))
        ttk.Label(status_bar, text="状态:").pack(side=tk.LEFT)
        ttk.Label(status_bar, textvariable=self.var_status, foreground="#0066CC").pack(side=tk.LEFT, padx=(4, 0))

        self.progress = ttk.Progressbar(status_bar, mode="indeterminate", length=180)
        self.progress.pack(side=tk.RIGHT)

    def _row_path(self, parent: ttk.Frame, row: int, label: str, var: tk.StringVar, *, browse: bool) -> None:
        ttk.Label(parent, text=label + "：").grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky=tk.EW, padx=(0, self.PADDING))
        if browse:
            ttk.Button(parent, text="浏览…", width=8, command=lambda v=var: self._browse_dir(v)).grid(row=row, column=2)

    def _browse_dir(self, var: tk.StringVar) -> None:
        initial = var.get() or str(Path.cwd())
        chosen = filedialog.askdirectory(initialdir=initial, mustexist=False, parent=self.root, title="选择目录")
        if chosen:
            var.set(os.path.normpath(chosen))

    # -------------------------------------------------------------------
    # 事件回调
    # -------------------------------------------------------------------
    def _on_start(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("提示", "已有任务在运行，请先等待结束。")
            return

        try:
            session_yaml = self._build_session_yaml()
        except Exception as e:
            messagebox.showerror("配置错误", f"无法生成会话配置：{e}")
            return

        self.btn_start.configure(state=tk.DISABLED)
        self.btn_open_excel.configure(state=tk.DISABLED)
        self.var_status.set("运行中…")
        self.progress.start(80)
        self.last_excel_path = None
        self.last_log_path = None

        self._append_log("================ 开始检测 ================\n", tag="ok")

        self.worker = threading.Thread(
            target=self._run_pipeline_worker,
            args=(session_yaml,),
            daemon=True,
        )
        self.worker.start()

    def _on_save_yaml(self) -> None:
        try:
            text = self._render_yaml_text(persist=True)
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.write_text(text, encoding="utf-8")
            messagebox.showinfo("已保存", f"已写入 {self.config_path}")
            self._append_log(f"已保存当前界面值到 {self.config_path}\n", tag="ok")
        except Exception as e:
            messagebox.showerror("保存失败", str(e))

    def _on_clear_log(self) -> None:
        self.log_widget.configure(state=tk.NORMAL)
        self.log_widget.delete("1.0", tk.END)
        self.log_widget.configure(state=tk.DISABLED)

    def _on_diagnose(self) -> None:
        """选一张 jpg，先「整图 OCR」再「按当前裁剪框 OCR」对比，结果贴日志。"""
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("提示", "已有任务在运行，请先等待结束。")
            return

        initial = self.var_jpg.get() or str(Path.cwd())
        chosen = filedialog.askopenfilename(
            initialdir=initial,
            parent=self.root,
            title="选择一张要诊断的 JPG",
            filetypes=[("JPEG", "*.jpg *.jpeg"), ("所有文件", "*.*")],
        )
        if not chosen:
            return

        self.btn_diagnose.configure(state=tk.DISABLED)
        self.var_status.set("诊断中…")
        self.progress.start(80)

        crop = (
            int(self.var_crop_x.get()),
            int(self.var_crop_y.get()),
            int(self.var_crop_w.get()),
            int(self.var_crop_h.get()),
        )
        regex = self.cfg.ocr.timecode_regex
        lang = self.var_lang.get() or "ch"
        use_gpu = bool(self.var_use_gpu.get())

        threading.Thread(
            target=self._run_diagnose,
            args=(chosen, regex, lang, use_gpu, crop),
            daemon=True,
        ).start()

    def _run_diagnose(self, img_path: str, regex: str, lang: str, use_gpu: bool, crop) -> None:
        from .ocr_worker import diagnose_image

        try:
            self.log_queue.put(f"================ 单图诊断: {Path(img_path).name} ================")
            full = diagnose_image(img_path, lang=lang, use_gpu=use_gpu, regex=regex, crop=None)
            self.log_queue.put(f"[整图] 尺寸={full.get('image_size')}")
            if not full["ok"]:
                self.log_queue.put(f"[整图] ERROR {full.get('error', '')}")
            else:
                self.log_queue.put(f"[整图] OCR 全部识别文本: {full['raw_texts']}")
                self.log_queue.put(f"[整图] 匹配时间码 ({regex}): {full['matched']}")

            cropped = diagnose_image(img_path, lang=lang, use_gpu=use_gpu, regex=regex, crop=crop)
            self.log_queue.put(f"[裁剪] 裁剪框={crop}  实际尺寸={cropped.get('image_size')}")
            if not cropped["ok"]:
                self.log_queue.put(f"[裁剪] ERROR {cropped.get('error', '')}")
            else:
                self.log_queue.put(f"[裁剪] OCR 全部识别文本: {cropped['raw_texts']}")
                self.log_queue.put(f"[裁剪] 匹配时间码: {cropped['matched']}")

            # 给出建议
            if full["ok"] and cropped["ok"]:
                if cropped["matched"]:
                    self.log_queue.put("[建议] 当前裁剪框可识别到时间码，参数 OK。")
                elif full["matched"]:
                    self.log_queue.put("[建议] 整图能识别但裁剪框丢了 OSD：请调整裁剪 X/Y/宽/高。")
                elif full["raw_texts"]:
                    self.log_queue.put(f"[建议] OCR 识别到文本但不匹配 {regex}；请检查时间码格式或修改正则。")
                else:
                    self.log_queue.put("[建议] OCR 未识别到任何文本：图像过暗/模糊或非时间码画面。")
        except Exception as e:
            import traceback
            self.log_queue.put("[诊断异常]\n" + traceback.format_exc())
        finally:
            self.root.after(0, self._on_diagnose_done)

    def _on_diagnose_done(self) -> None:
        self.progress.stop()
        self.btn_diagnose.configure(state=tk.NORMAL)
        self.var_status.set("就绪")

    def _on_open_excel(self) -> None:
        if self.last_excel_path and Path(self.last_excel_path).exists():
            self._open_path(str(self.last_excel_path))
        else:
            messagebox.showwarning("尚无报告", "请先成功运行一次检测。")

    def _open_path(self, path_str: str) -> None:
        if not path_str:
            return
        p = Path(path_str)
        if not p.exists():
            messagebox.showwarning("路径不存在", f"{p} 不存在")
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(p))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(p)])
            else:
                subprocess.Popen(["xdg-open", str(p)])
        except Exception as e:
            messagebox.showerror("打开失败", str(e))

    # -------------------------------------------------------------------
    # 工作线程
    # -------------------------------------------------------------------
    def _run_pipeline_worker(self, session_yaml: Path) -> None:
        from .pipeline import run as pipeline_run  # 延迟 import，避免 GUI 启动卡 PaddleOCR

        exit_code = 1
        try:
            exit_code = pipeline_run(session_yaml)
        except Exception:
            self.log_queue.put("[GUI] 流水线意外异常:\n" + traceback.format_exc())
        finally:
            self.root.after(0, self._on_finish, exit_code, session_yaml)

    def _on_finish(self, exit_code: int, session_yaml: Path) -> None:
        self.progress.stop()
        self.btn_start.configure(state=tk.NORMAL)
        success = (exit_code == 0)
        self.var_status.set(f"完成（退出码 {exit_code}）" if success else f"失败（退出码 {exit_code}）")

        # 解析最近的 excel / log
        excel_dir = Path(self.var_excel.get())
        log_dir = Path(self.var_log.get())
        self.last_excel_path = self._find_latest(excel_dir, "Sync_n_Timecode_", ".xlsx")
        self.last_log_path = self._find_latest(log_dir, "run_", ".log")

        if self.last_excel_path:
            self.btn_open_excel.configure(state=tk.NORMAL)

        msg = "检测完成" if success else f"检测失败（退出码 {exit_code}）"
        if self.last_excel_path:
            msg += f"\nExcel 报告：{self.last_excel_path}"
        if self.last_log_path:
            msg += f"\n日志：{self.last_log_path}"

        self._append_log(f"================ {msg} ================\n", tag="ok" if success else "err")

        try:
            session_yaml.unlink(missing_ok=True)
        except Exception:
            pass

        if success:
            messagebox.showinfo("完成", msg)
        else:
            messagebox.showerror("失败", msg)

    @staticmethod
    def _find_latest(folder: Path, prefix: str, suffix: str) -> Optional[Path]:
        if not folder.exists():
            return None
        items = [
            p for p in folder.iterdir()
            if p.is_file() and p.name.startswith(prefix) and p.name.endswith(suffix)
        ]
        if not items:
            return None
        return max(items, key=lambda p: p.stat().st_mtime)

    # -------------------------------------------------------------------
    # 日志轮询
    # -------------------------------------------------------------------
    def _poll_log(self) -> None:
        try:
            for _ in range(200):
                line = self.log_queue.get_nowait()
                tag = None
                if "[ERROR]" in line or "❌" in line or "Traceback" in line:
                    tag = "err"
                elif "[WARNING]" in line or "[诊断]" in line:
                    tag = "warn"
                elif (
                    "✅" in line
                    or "[OK]" in line
                    or ("步骤" in line and "完成" in line)
                    or "Synchronization rate:" in line
                    or "总耗时:" in line
                    or "程序结束时间:" in line
                    or "检测完成" in line
                    or line.strip().startswith("================")
                ):
                    tag = "ok"
                elif "[INFO]" in line and (
                    "成功" in line or "completed" in line.lower() or "==" in line
                ):
                    tag = "ok"
                self._append_log(line + "\n", tag=tag)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._poll_log)

    def _append_log(self, text: str, *, tag: Optional[str] = None) -> None:
        self.log_widget.configure(state=tk.NORMAL)
        if tag:
            self.log_widget.insert(tk.END, text, tag)
        else:
            self.log_widget.insert(tk.END, text)
        self.log_widget.see(tk.END)
        self.log_widget.configure(state=tk.DISABLED)

    # -------------------------------------------------------------------
    # 配置 IO
    # -------------------------------------------------------------------
    def _build_session_yaml(self) -> Path:
        """把界面当前值写入临时 YAML，返回路径；强制 ``pause_before_exit=false``。"""
        text = self._render_yaml_text(persist=False)
        tmp_dir = Path(tempfile.gettempdir()) / "camera_sync_session"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = tmp_dir / f"session_{os.getpid()}.yaml"
        tmp_path.write_text(text, encoding="utf-8")
        return tmp_path

    def _render_yaml_text(self, *, persist: bool) -> str:
        """构造完整 YAML 文本（保留全部字段以兼容 load_config）。"""
        data = {
            "paths": {
                "cr2_dir":   self.var_cr2.get(),
                "jpg_dir":   self.var_jpg.get(),
                "false_dir": self.var_false.get(),
                "excel_dir": self.var_excel.get(),
                "log_dir":   self.var_log.get(),
            },
            "crop": {
                "x":      int(self.var_crop_x.get()),
                "y":      int(self.var_crop_y.get()),
                "width":  int(self.var_crop_w.get()),
                "height": int(self.var_crop_h.get()),
            },
            "ocr": {
                "lang":            self.var_lang.get() or "ch",
                "use_gpu":         bool(self.var_use_gpu.get()),
                "timecode_regex":  self.cfg.ocr.timecode_regex,
                "force_hour_zero": bool(self.var_force_zero.get()),
            },
            "runtime": {
                "max_workers":            int(self.var_workers.get()),
                "fail_fast_on_ocr_error": self.cfg.runtime.fail_fast_on_ocr_error,
            },
            "excel": {
                "filename_prefix": self.cfg.excel.filename_prefix,
                "highlight_color": self.cfg.excel.highlight_color,
            },
            "pipeline": {
                "do_clear_jpg_dir":   self.cfg.pipeline.do_clear_jpg_dir,
                "do_cr2_to_jpg":      self.cfg.pipeline.do_cr2_to_jpg,
                "do_ocr_report":      self.cfg.pipeline.do_ocr_report,
                "do_clear_false_dir": self.cfg.pipeline.do_clear_false_dir,
                "do_copy_false":      self.cfg.pipeline.do_copy_false,
            },
            "ui": {
                # GUI 模式必须关闭，否则 pipeline 末尾会 input() 阻塞工作线程
                "pause_before_exit": False if not persist else self.cfg.ui.pause_before_exit,
            },
        }
        return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


# ---------------------------------------------------------------------------
# 公共入口
# ---------------------------------------------------------------------------
def run_gui(config_path: Optional[os.PathLike] = None) -> int:
    """启动 GUI 主循环；返回进程退出码（GUI 正常关闭返回 0）。"""
    cfg_path = Path(config_path) if config_path else default_config_path()
    try:
        root = tk.Tk()
    except tk.TclError as e:
        # 没有图形会话时（例如 SSH 无 DISPLAY）回退到控制台模式
        sys.stderr.write(f"[GUI] 无法初始化 Tk ({e})；请使用 --cli 控制台模式。\n")
        return 5

    try:
        CameraSyncGUI(root, cfg_path)
    except ConfigError as e:
        messagebox.showerror("配置错误", str(e))
        return 2

    root.mainloop()
    return 0
