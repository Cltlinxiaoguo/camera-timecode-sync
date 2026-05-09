# 相机同步检测工具

将原 4 个 Python 脚本（`Cr2 Cut Into Jpg.py` / `CS8K_n_Timecode.py` / `Copy_False.py` / `Clear_folder.py`）重构、模块化、配置外置，并打包为 Windows 单文件可执行程序 **`相机同步检测工具.exe`**：目标机器无需安装 Python，双击即可跑通"清空 → CR2 转 JPG → OCR → Excel 报告 → 复制不同步图"全流程。

**两种使用形态：**
- **图形界面（GUI，默认）**：双击 exe 弹出 Tkinter 窗口，三个目录选择器 + 开始按钮 + 实时滚动日志 + 一键打开报告/异常归档/日志目录。
- **控制台模式**：`exe --cli` 走原命令行流水线，便于脚本化或定时任务调用。

> 配套文档：
> - [需求与设计](./相机同步检测工具_需求与设计.md)
> - [测试用例与自动化](./相机同步检测工具_测试用例与自动化.md)
> - [发布到 GitHub（Release 流程）](./docs/release.md)

**下载安装（给最终用户）**：请到你维护的 **GitHub Releases**（建议单独建业务仓库，例如 `camera-sync-tool`，不要用「用户名同名的 profile 仓库」放整项目）下载最新 **`相机同步检测工具.exe`**，与同目录的 `camera_sync_config.yaml` 一起使用。`dist/` 不会进 Git 主分支；首次上传大体积请走 **Release 附件**，见 [docs/release.md](./docs/release.md)。

---

## 1. 目录结构

```
.
├── main.py                                # 入口（PyInstaller 打包目标）
├── camera_sync/                           # 业务包
│   ├── config.py                          # YAML 加载与校验
│   ├── logging_setup.py                   # 控制台 + 文件日志（UTF-8）
│   ├── clear_folder.py                    # 清空目录但保留目录本身
│   ├── timecode.py                        # 时间码纯函数（可单测）
│   ├── cr2_to_jpg.py                      # rawpy 读 CR2 → 裁剪 → JPG
│   ├── ocr_worker.py                      # 多进程 OCR worker（每 worker 仅初始化一次 PaddleOCR）
│   ├── ocr_report.py                      # 进程池调度 + 汇总
│   ├── excel_writer.py                    # DataFrame → xlsx + 高亮 + 饼图
│   ├── copy_false.py                      # 按 IsSame=False 复制图片
│   ├── pipeline.py                        # 主流水线串联
│   └── gui.py                             # Tkinter GUI（默认入口）
├── docs/                                  # 发布与维护说明（如 GitHub Release）
├── scripts/                               # 辅助脚本（如上传 Release）
├── camera_sync_config.yaml                # 默认配置（带中文注释）
├── camera_sync.spec                       # PyInstaller 规格
├── tests/                                 # pytest 单元 / 集成 smoke
├── pytest.ini
├── run_tests.bat                          # Windows 一键测试
├── requirements.txt                       # 运行时依赖
├── requirements-dev.txt                   # 开发 + 测试依赖
├── 原脚本/                                # 原始 4 脚本（仅参考，未被打包）
└── README.md
```

---

## 2. 现场使用（最终用户）

> 适用 **目标机零 Python 环境**：

把 `相机同步检测工具.exe` + `camera_sync_config.yaml` 放到同一文件夹。如果 yaml 不存在，首次启动会自动写出默认模板。

### 2.1 推荐流程：图形界面（GUI）

**双击 `相机同步检测工具.exe`** 直接打开窗口：

```
┌──────────────────────────────────────────────────────────┐
│ 相机同步检测工具                                           │
├──────────────────────────────────────────────────────────┤
│ ┌── 路径 ─────────────────────────────────────────────┐  │
│ │ CR2 输入目录:    [_______________]  [浏览…]         │  │
│ │ JPG 中间目录:    [_______________]  [浏览…]         │  │
│ │ 异常归档目录:    [_______________]  [浏览…]         │  │
│ │ Excel 报告目录:  [_______________]  [浏览…]         │  │
│ │ 日志目录:        [_______________]  [浏览…]         │  │
│ └────────────────────────────────────────────────────┘  │
│ ┌── 参数 ─────────────────────────────────────────────┐  │
│ │ 裁剪 X:[740] Y:[2240] 宽:[1621] 高:[1428]            │  │
│ │ OCR 语种:[ch▼] 并发数:[2▲] ☑ 强制小时位归零 ☐ GPU   │  │
│ └────────────────────────────────────────────────────┘  │
│ [开始检测][保存到 YAML][清空日志][打开最近报告] …         │
│ ┌── 日志 ─────────────────────────────────────────────┐  │
│ │ 2026-05-08 [INFO] camera_sync.pipeline: 启动          │  │
│ │ 2026-05-08 [INFO] camera_sync.cr2_to_jpg: ...         │  │
│ │ ...                                                  │  │
│ └────────────────────────────────────────────────────┘  │
│ 状态: 运行中…                              [▮▮▮▮▮▮▯▯▯]   │
└──────────────────────────────────────────────────────────┘
```

操作要点：
1. 用 **「浏览…」** 选择 CR2 输入 / JPG 中间 / 异常归档 / Excel / 日志 五个目录（启动时已从 YAML 预填）。
2. 调整裁剪框、OCR 语种、并发数等参数。
3. 点 **「开始检测」**：流水线在后台线程跑，日志实时滚到下方文本框；运行期按钮自动禁用，结束后弹窗汇总并自动启用「打开最近报告」。
4. 点 **「保存到 YAML」** 把当前界面值持久化回 `camera_sync_config.yaml`，下次启动直接复用。
5. 「打开 Excel 目录 / 异常归档 / 日志目录」 按钮一键调出对应资源管理器窗口。

### 2.2 控制台模式（脚本化 / 老用户）

```bat
:: 与同目录 yaml 配合
相机同步检测工具.exe --cli

:: 指定其它配置
相机同步检测工具.exe --cli "D:\custom.yaml"

:: 帮助
相机同步检测工具.exe --help
```

控制台模式行为与之前一致：
- 控制台滚动输出每张图识别结果，`[OK]` / `[NG]` 一目了然；
- 结束时显示同步率统计；
- 默认提示 **"按回车键退出"**（YAML 中 `ui.pause_before_exit: false` 可关闭）；
- Excel 报告位于 `paths.excel_dir`，文件名带运行时间戳，**不会覆盖历史**；
- 不同步图片自动归档到 `paths.false_dir`；
- 完整日志位于 `paths.log_dir/run_<时间戳>.log`，UTF-8 编码。

### 2.3 现场需要修改的最小项

| 字段 | 默认值 | 现场必改？ |
|------|--------|-----------|
| `paths.cr2_dir`   | `C:\Users\Administrator\...\photo`（原脚本作者机器路径） | **是** |
| `paths.jpg_dir`   | `C:\Pycahrmproject\frames` | 视盘符可保留 |
| `paths.false_dir` | `C:\Pycahrmproject\false` | 视盘符可保留 |
| `crop.*`          | 740 / 2240 / 1621 / 1428 | 仅在 OSD 位置变化时改 |
| 其它              | 一般保持 | — |

---

## 3. 开发与测试

### 3.1 安装开发依赖

```powershell
# 推荐使用虚拟环境
python -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

> `requirements.txt` 含 `paddleocr` / `paddlepaddle` / `rawpy` 等运行时大依赖；`requirements-dev.txt` 在此基础上加上 `pytest` / `pyinstaller` / `freezegun`。  
> 仅跑单元测试时**不需要**安装 paddleocr/rawpy/cv2，缺失这些库测试会自动绕开（详见 [测试用例与自动化](./相机同步检测工具_测试用例与自动化.md) 第 4 节 mock 说明）。

### 3.2 运行测试

```bat
:: Windows 一键（默认排除 slow）
run_tests.bat
```

```bash
# 跨平台等价
python -m pytest -q -m "not slow"
```

```bash
# 覆盖率
python -m pytest -q -m "not slow" --cov=camera_sync --cov-report=term-missing
```

### 3.3 直接调试运行（不打包）

```powershell
python main.py                                  # 默认 GUI，用同目录 yaml
python main.py --cli                            # 控制台模式
python main.py --cli "D:\其他位置\custom.yaml"  # 控制台 + 指定 yaml
python main.py --help                           # 命令行参数帮助
```

---

## 4. 打包为 exe

```powershell
# 在已安装运行时依赖的环境下
pyinstaller --clean camera_sync.spec
```

产物：

```
dist\相机同步检测工具.exe
```

> 体积说明：onefile + PaddleOCR + paddle + cv2 实测约 1~1.5 GB；首次启动会临时解压，需要等待几秒到十几秒。这是 PyInstaller + 该技术栈的固有现象，**已在 PRD P4 中说明并接受**。

---

## 5. 与原脚本的关系（变更摘要）

| 原脚本 | 重构对应 | 行为变更 |
|--------|----------|----------|
| `Clear_folder.py` | `camera_sync/clear_folder.py` | 改用 logger 输出；不存在的目录可选自动创建 |
| `Cr2 Cut Into Jpg.py` | `camera_sync/cr2_to_jpg.py` | 路径 / 裁剪移入 YAML；单文件失败不再中断流程；增加 imageio 失败时 cv2 兜底，兼容中文路径 |
| `CS8K_n_Timecode.py` | `camera_sync/ocr_worker.py` + `excel_writer.py` + `ocr_report.py` | **修复**：跳过 Summary 行的高亮 Bug（原 `max_row=len(final_df)-1` 漏最后一行）；多进程改用 `initializer` 让每个 worker 仅初始化一次 PaddleOCR |
| `Copy_False.py` | `camera_sync/copy_false.py` | Excel 路径改由 pipeline 动态传入；Summary 行强制跳过 |

---

## 6. 配置项速查

完整注释见 [`camera_sync_config.yaml`](./camera_sync_config.yaml)。

| 节 | 字段 | 默认 | 说明 |
|----|------|------|------|
| paths | cr2_dir | `C:\...\photo` | CR2 输入目录 |
| paths | jpg_dir | `C:\Pycahrmproject\frames` | 中间 JPG 输出（每次清空）|
| paths | false_dir | `C:\Pycahrmproject\false` | 不同步图归档（每次清空）|
| paths | excel_dir | `''` (=exe 同目录) | Excel 报告输出 |
| paths | log_dir | `''` (=exe/logs) | 日志目录 |
| crop | x / y / width / height | 740 / 2240 / 1621 / 1428 | 与原脚本一致 |
| ocr | lang | `'ch'` | PaddleOCR 语种 |
| ocr | timecode_regex | `\d{2}:\d{2}:\d{2}:\d{2}` | 时间码正则 fullmatch |
| ocr | force_hour_zero | `true` | 首段强制归零（消除小时位差）|
| runtime | max_workers | `0` (auto) | OCR 进程数；0 表示 `min(8, cpu)` |
| runtime | fail_fast_on_ocr_error | `false` | 单图失败是否中止整体 |
| excel | filename_prefix | `Sync_n_Timecode` | 报告文件名前缀 |
| excel | highlight_color | `FFCCCC` | 不同步行填充色 |
| pipeline | do_clear_jpg_dir 等 5 个开关 | `true` | 调试时可关 |
| ui | pause_before_exit | `true` | 结束按回车退出 |

---

## 7. 退出码语义

| 退出码 | 含义 |
|--------|------|
| 0 | 成功 |
| 1 | 流水线异常终止（已写入日志）|
| 2 | 配置加载失败 |
| 3 | CR2 转 JPG 全部失败 |
| 4 | OCR 没有输入或未生成 Excel |
| 5 | GUI 初始化失败（无图形会话）；建议改用 `--cli`，main.py 已自动回退 |
| 130 | 用户 Ctrl+C |

---

## 8. 验收清单（与 PRD 对齐）

- [x] 双击 exe 全流程跑通：清空 → CR2→JPG → OCR → Excel → 复制不同步图（TC-ACC-001）
- [x] Excel 文件名带时间戳；同步率饼图；False 行红色高亮；Summary 行不被高亮（TC-EXCEL-003 / TC-EXCEL-004）
- [x] PaddleOCR 子进程仅初始化一次（`ProcessPoolExecutor(initializer=...)`）
- [x] 配置文件 YAML，与 exe 同目录，**修改后无需重新打包**（TC-ACC-002 / TC-ACC-003）
- [x] 异常捕获并记录日志，避免无声崩溃（TC-PIPELINE-003）
- [x] UTF-8 控制台与日志（TC-LOG-001）
- [x] 结束提示按回车退出（TC-ACC-004）

---

*Last updated: 与开发计划同步维护。*
