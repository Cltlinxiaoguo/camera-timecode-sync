import os
import shutil


def clear_folder_contents(folder_path):
    """
    清除指定文件夹内的所有文件和子文件夹，但保留文件夹本身。

    参数:
        folder_path (str): 要清除的文件夹的完整路径。
    """
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)  # 删除文件或符号链接
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)  # 删除目录及目录下的所有内容
        except Exception as e:
            print(f'Failed to delete {file_path}. Reason: {e}')


# 使用示例：
# folder_to_clean = r'C:\Pycahrmproject\frames'
# clear_folder_contents(folder_to_clean)