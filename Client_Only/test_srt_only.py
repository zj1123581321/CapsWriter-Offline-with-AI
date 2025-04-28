#!/usr/bin/env python
# coding: utf-8

"""
测试只生成SRT文件的功能
"""

import sys
import os
from pathlib import Path

# 添加父目录到sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

# 导入转录模块
from Client_Only import transcribe, Config

def main():
    # 测试文件路径
    file_path = "D:\\MyFolders\\Developments\\0Python\\250427_VideoTranscriptApi\\sample_files\\test_files\\29108798989-1-30232.m4s"
    
    # 确保文件存在
    if not os.path.exists(file_path):
        print(f"错误: 文件不存在: {file_path}")
        return
    
    # 显示配置
    print("=== 当前配置 ===")
    print(f"服务器: {Config.server_addr}:{Config.server_port}")
    print(f"生成SRT: {Config.generate_srt}")
    print(f"生成TXT: {Config.generate_txt}")
    print(f"生成合并TXT: {Config.generate_merge_txt}")
    print(f"生成JSON: {Config.generate_json}")
    print("===============")
    
    # 转录文件
    print(f"\n开始转录文件: {file_path}")
    success, files = transcribe(file_path)
    
    # 显示结果
    if success:
        print("\n=== 转录成功 ===")
        if files:
            print(f"生成了 {len(files)} 个文件:")
            for f in files:
                print(f"  - {f}")
                
            # 检查是否只有SRT文件
            only_srt = all(Path(f).suffix.lower() == '.srt' for f in files)
            if only_srt:
                print("\n[成功] 只生成了SRT文件，测试通过!")
            else:
                print("\n[失败] 生成了非SRT文件，测试失败!")
        else:
            print("未生成任何文件")
    else:
        print("\n=== 转录失败 ===")
    
    # 检查其他文件是否存在
    base_path = Path(file_path).with_suffix("")
    txt_file = base_path.with_suffix(".txt")
    json_file = base_path.with_suffix(".json")
    merge_txt_file = base_path.with_suffix(".merge.txt")
    
    unexpected_files = []
    if not Config.generate_txt and txt_file.exists():
        unexpected_files.append(txt_file)
    if not Config.generate_json and json_file.exists():
        unexpected_files.append(json_file)
    if not Config.generate_merge_txt and merge_txt_file.exists():
        unexpected_files.append(merge_txt_file)
    
    if unexpected_files:
        print("\n[警告] 发现意外生成的文件:")
        for f in unexpected_files:
            print(f"  - {f}")
    else:
        print("\n没有发现意外生成的文件")

if __name__ == "__main__":
    main() 