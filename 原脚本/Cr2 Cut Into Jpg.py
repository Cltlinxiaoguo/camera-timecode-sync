import os
import rawpy
import imageio
from Clear_folder import clear_folder_contents

# 清除上一次文件夹记录(调条用了同级目录脚本的函数)
folder_to_clean = r'C://Pycahrmproject//frames'
clear_folder_contents(folder_to_clean)

# 指定路径
input_path = r"C:\Users\Administrator\Documents\Colorlight\Calibration\Projects\CS16K同步测试-长时间播放\photo"
# input_path = r"C:\Users\Administrator\Documents\Colorlight\Calibration\Projects\长时间播放多机同步测试\4k_60hz_h265"
output_path = r"C:\Pycahrmproject\frames"

# 确保输出路径存在
os.makedirs(output_path, exist_ok=True)

# 定义裁剪区域：起点 (x, y)，宽度和高度
crop_x, crop_y = 740, 2240
crop_width, crop_height = 1621, 1428

# 遍历指定路径下的所有文件
for filename in os.listdir(input_path):
    # 检查文件是否为 .cr2 格式
    if filename.lower().endswith(".cr2"):
        # 构造完整路径
        cr2_file_path = os.path.join(input_path, filename)
        jpg_file_path = os.path.join(output_path, os.path.splitext(filename)[0] + ".jpg")

        # 使用 rawpy 读取 .cr2 文件
        with rawpy.imread(cr2_file_path) as raw:
            # 将 RAW 图像转换为 RGB 格式
            rgb_image = raw.postprocess()

        # 裁剪指定区域
        cropped_image = rgb_image[
            crop_y:crop_y + crop_height,
            crop_x:crop_x + crop_width
        ]

        # 使用 imageio 保存为 .jpg 格式
        imageio.imsave(jpg_file_path, cropped_image)
        print(f"Converted and cropped: {cr2_file_path} -> {jpg_file_path}")

print("All conversions completed.")