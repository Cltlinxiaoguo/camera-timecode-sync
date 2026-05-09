# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 规格文件 - 相机同步检测工具

构建命令（Windows）：
    chcp 65001
    pyinstaller --clean camera_sync.spec

产物：
    dist/相机同步检测工具.exe   (单文件、无控制台，仅 GUI)

要点：
- onefile + windowed（console=False），双击打开展示 UI，不弹出黑色控制台；
- 进度与错误见 GUI 日志区与 ``logs/run_*.log``；若需命令行批处理，请用源码 ``python main.py --cli``；
- 收集 paddleocr / paddle / cv2 / rawpy / matplotlib 隐藏依赖与数据文件；
- 排除 IPython / notebook / 测试框架等无用大依赖以减小体积；
- exe 同目录的 camera_sync_config.yaml 不打入 exe（保证修改后无需重新打包）。
"""
from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
    copy_metadata,
)


block_cipher = None

hiddenimports = []
datas = []
binaries = []

# --- PaddleOCR / Paddle 隐藏依赖 ---
# paddleocr 用 _import_file() 按文件路径动态加载 paddleocr/tools/__init__.py
# 等子模块 —— 这种"非标准 Python import"在 PyInstaller 下不会被 collect_submodules
# 自动复制源码，必须把 paddleocr 包整体作为 *数据文件* 打包（include_py_files=True）。
for pkg in ("paddleocr", "paddle", "shapely", "pyclipper", "skimage", "lmdb"):
    try:
        hiddenimports += collect_submodules(pkg)
    except Exception:
        pass
    try:
        if pkg == "paddleocr":
            datas += collect_data_files(pkg, include_py_files=True)
        else:
            datas += collect_data_files(pkg)
    except Exception:
        pass
    try:
        datas += copy_metadata(pkg)
    except Exception:
        pass

# --- rawpy / imageio / cv2 / openpyxl 数据文件 ---
for pkg in ("rawpy", "imageio", "imageio_ffmpeg", "cv2", "openpyxl", "matplotlib"):
    try:
        datas += collect_data_files(pkg)
    except Exception:
        pass

# --- Cython / setuptools 运行时模板文件 ---
# paddle 在 import 阶段会沿链触达 paddle.utils.cpp_extension → setuptools.build_ext
# → Cython.Compiler.Main → 加载 Cython/Utility/*.cpp / *.pyx / *.pxd 模板。
# 这些是非 Python 数据文件，PyInstaller 默认不收集，需显式打包，否则首次 OCR
# 子进程初始化阶段会抛 FileNotFoundError: ...\Cython\Utility\CppSupport.cpp。
# 对应日志见 issue「FileNotFoundError: ...Cython\Utility\CppSupport.cpp」。
for pkg in ("Cython", "setuptools"):
    try:
        datas += collect_data_files(pkg, include_py_files=False)
    except Exception:
        pass
    try:
        hiddenimports += collect_submodules(pkg)
    except Exception:
        pass

# --- Tkinter 显式声明，PyInstaller 默认会自动收集，这里加固确保 GUI 可用 ---
hiddenimports += ["tkinter", "tkinter.ttk", "tkinter.filedialog", "tkinter.messagebox"]

# 排除以减小体积
# 注意：tkinter 必须保留（GUI 模式依赖）；IPython / notebook / Qt 可剔除。
excludes = [
    "IPython",
    "notebook",
    "jupyter",
    "pytest",
    "pytest_cov",
    "tests",
    "PyQt5",
    "PyQt6",
    "PySide2",
    "PySide6",
]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='相机同步检测工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
