#!/usr/bin/env python
# coding: utf-8

"""
转录特定文件，只生成SRT字幕
"""

import sys
from pathlib import Path

# 添加当前目录的父目录到sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

# 导入转录模块
from Client_Only import transcribe

def main():
    # 要转录的文件路径
    file_path = "D:\\MyFolders\\Developments\\0Python\\250427_VideoTranscriptApi\\sample_files\\test_files\\29108798989-1-30232.m4s"
    
    print(f"开始转录文件: {file_path}")
    print("仅生成SRT字幕文件")
    
    # 执行转录
    success, files = transcribe(file_path)
    
    if success:
        if files:
            print(f"\n转录成功！生成了以下文件:")
            for f in files:
                print(f"  - {f}")
        else:
            print("\n转录完成，但未生成任何文件")
    else:
        print("\n转录失败")

if __name__ == "__main__":
    main() 