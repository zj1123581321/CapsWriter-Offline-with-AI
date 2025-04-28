import os
import sys
import subprocess
from pathlib import Path

# 设置要转录的视频文件路径
video_file = r"D:\Downloads\Video\Inbox\如何3秒钟看出一个人的实力奸商行走江湖7年的经验分享.mp4"

# 确保路径存在
if not os.path.exists(video_file):
    print(f"错误：找不到文件 {video_file}")
    sys.exit(1)

# 构建命令行调用
# 使用 python start_client.py 文件路径 的方式调用
command = f"python start_client.py \"{video_file}\""

print(f"开始转录视频: {video_file}")
print(f"执行命令: {command}")

# 执行命令
try:
    subprocess.run(command, shell=True, check=True)
    print("转录完成！")
    
    # 获取可能的输出文件路径
    base_path = Path(video_file).with_suffix("")
    txt_file = f"{base_path}.txt"
    srt_file = f"{base_path}.srt"
    
    if os.path.exists(txt_file):
        print(f"已生成文本文件: {txt_file}")
    
    if os.path.exists(srt_file):
        print(f"已生成字幕文件: {srt_file}")
        
except subprocess.CalledProcessError as e:
    print(f"转录失败：{e}")
except Exception as e:
    print(f"发生错误：{e}") 