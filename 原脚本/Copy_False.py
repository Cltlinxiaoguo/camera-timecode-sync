import pandas as pd
import shutil
from pathlib import Path
from Clear_folder import clear_folder_contents

# 清除上一次文件夹记录(调条用了同级目录脚本的函数)
folder_to_clean = r'C:\Pycahrmproject\false'
clear_folder_contents(folder_to_clean)

# Excel文件路径和工作表名称（如果适用）
excel_path = r'C:\Pycahrmproject\SynTest\Sync_n_Timecode_20260422_183240.xlsx'

sheet_name = 'Sheet1'  # 如果有特定的工作表，请指定名称；否则可以省略

# 指定路径
# source_dir = Path(r'C:\Pycahrmproject\NG')
source_dir = Path(r'C:\Pycahrmproject\frames')
destination_dir = Path(r'C:\Pycahrmproject\false')

# 确保目标路径存在
destination_dir.mkdir(parents=True, exist_ok=True)

# 读取Excel文档
df = pd.read_excel(excel_path, sheet_name=sheet_name)

# 打印所有列名，以便确认文件名列的实际名称
print("Columns in the Excel file:")
print(df.columns.tolist())

# 假设第4列 'Is Same' 是布尔值，并且文件名列名为 'Image Filename'
filename_col = 'Image Filename'
is_same_col = 'Is Same'

for index, row in df.iterrows():
    if not row[is_same_col]:  # 判断 'Is Same' 列结果为FALSE的数据
        filename = row[filename_col]  # 获取文件名列的值

        source_file = source_dir / filename
        destination_file = destination_dir / filename

        if source_file.exists():  # 检查文件是否存在
            shutil.copy2(source_file, destination_file)  # 复制文件并保留元数据
            print(f"Copied: {filename}")
        else:
            print(f"File not found: {filename}")

print("Operation completed.")