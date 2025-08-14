#!/usr/bin/env python
# coding: utf-8

from pathlib import Path
import sys
import typer
from core_client import init_file

if __name__ == "__main__":
    # 指定要转录的视频文件路径
    video_path = Path(r"D:\Downloads\Video\Inbox\如何3秒钟看出一个人的实力奸商行走江湖7年的经验分享.mp4")
    
    # 调用转录函数
    print(f"开始转录视频：{video_path}")
    typer.run(lambda: init_file([video_path]))
    
    # 转录完成后，输出文件会生成在视频文件同目录下
    print(f"转录完成！请查看生成的文本文件：{video_path.with_suffix('.txt')}")
    print(f"字幕文件路径：{video_path.with_suffix('.srt')}") 