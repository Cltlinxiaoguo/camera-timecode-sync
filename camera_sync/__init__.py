# -*- coding: utf-8 -*-
"""相机同步检测工具 - 包入口。

从 4 个原始脚本（Cr2 Cut Into Jpg.py / CS8K_n_Timecode.py /
Copy_False.py / Clear_folder.py）重构而来，模块划分如下：

- config        加载 / 校验 YAML 配置，提供默认模板写出
- logging_setup 控制台 + 文件双输出，UTF-8
- clear_folder  清空目录但保留目录本身
- timecode      时间码正则匹配 / 首段归零 / 同步判定（纯函数，可单测）
- cr2_to_jpg    遍历 CR2、按裁剪框输出 JPG
- ocr_worker    多进程 worker：每个进程仅初始化一次 PaddleOCR
- ocr_report    OCR 汇总 + DataFrame 构建 + Excel 生成 + 饼图
- excel_writer  Excel 写出（高亮 / Summary 行 / 饼图）独立可测
- copy_false    根据 Excel 中 Is Same==False 复制图片到归档目录
- pipeline      主流水线串联

外部仅需调用 camera_sync.pipeline.run(config_path)。
"""

__version__ = "1.0.0"
__all__ = ["__version__"]
