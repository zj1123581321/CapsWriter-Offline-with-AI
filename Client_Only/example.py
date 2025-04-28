#!/usr/bin/env python
# coding: utf-8

"""
CapsWriter转录模块使用示例
"""

import os
import sys
from pathlib import Path

# 添加当前目录的父目录到sys.path，使Python能够找到Client_Only包
sys.path.insert(0, str(Path(__file__).parent.parent))

# 导入转录模块
from Client_Only import transcribe, Config

def example_1():
    """基本用法示例"""
    # 要转录的文件路径
    file_path = "D:/MyFolders/Developments/0Python/250427_VideoTranscriptApi/sample_files/test_files/29108798989-1-30232.m4s"
    
    # 设置服务器地址和端口
    Config.server_addr = "100.89.110.76"
    Config.server_port = 6016
    
    # 执行转录
    success, files = transcribe(file_path)
    
    if success:
        print(f"转录成功！生成了以下文件:")
        for f in files:
            print(f"  - {f}")
    else:
        print("转录失败")

def example_2():
    """使用参数覆盖配置"""
    # 要转录的文件路径
    file_path = "D:/Downloads/test_video.mp4"
    
    # 使用参数形式设置配置
    success, files = transcribe(
        file_path,
        server_addr="127.0.0.1",
        server_port=6007,
        generate_json=False,  # 不生成JSON文件
        generate_merge_txt=False,  # 不生成合并文本文件
    )
    
    if success:
        print(f"转录成功！生成了以下文件:")
        for f in files:
            print(f"  - {f}")
    else:
        print("转录失败")

async def example_3_async():
    """异步API使用示例"""
    import asyncio
    from Client_Only import transcribe_async
    
    # 要转录的文件路径
    file_path = "D:/Downloads/test_video.mp4"
    
    # 使用异步API
    success, files = await transcribe_async(
        file_path,
        server_addr="127.0.0.1",
        server_port=6007,
    )
    
    if success:
        print(f"异步转录成功！生成了以下文件:")
        for f in files:
            print(f"  - {f}")
    else:
        print("异步转录失败")

def example_4_batch():
    """批量转录示例"""
    # 要转录的文件目录
    directory = "D:/Downloads/Videos"
    
    # 获取目录中的所有视频文件
    video_extensions = [".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv"]
    video_files = []
    
    for ext in video_extensions:
        video_files.extend(list(Path(directory).glob(f"*{ext}")))
    
    # 设置服务器信息
    Config.server_addr = "127.0.0.1"
    Config.server_port = 6007
    
    # 批量转录
    print(f"找到 {len(video_files)} 个视频文件，开始批量转录...")
    
    for i, file_path in enumerate(video_files):
        print(f"\n[{i+1}/{len(video_files)}] 转录文件: {file_path}")
        
        success, files = transcribe(str(file_path))
        
        if success:
            print(f"  转录成功! 生成了 {len(files)} 个文件")
        else:
            print(f"  转录失败")

if __name__ == "__main__":
    # 运行示例1
    example_1()
    
    # 要运行异步示例，取消下面的注释
    # import asyncio
    # asyncio.run(example_3_async()) 