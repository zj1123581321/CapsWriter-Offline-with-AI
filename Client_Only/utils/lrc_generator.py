#!/usr/bin/env python
# coding: utf-8

"""
LRC歌词/字幕生成工具
"""

import json
import math
from pathlib import Path

def format_time_lrc(seconds):
    """
    将秒数格式化为LRC时间格式 [mm:ss.xx]
    
    参数:
        seconds: 秒数
        
    返回:
        str: 格式化的时间字符串
    """
    # 处理负数时间
    if seconds < 0:
        seconds = 0
        
    # 计算分钟和秒
    minutes = math.floor(seconds / 60)
    seconds_remainder = seconds % 60
    centiseconds = math.floor((seconds_remainder - math.floor(seconds_remainder)) * 100)
    
    # 格式化为 [mm:ss.xx]
    return f"[{minutes:02d}:{math.floor(seconds_remainder):02d}.{centiseconds:02d}]"

def generate_lrc_from_json(json_file):
    """
    从JSON文件直接生成LRC字幕文件
    
    参数:
        json_file: JSON文件路径，包含时间戳和标记信息
        
    返回:
        str: 生成的LRC文件路径
    """
    json_path = Path(json_file)
    lrc_path = json_path.with_suffix('.lrc')
    
    # 检查文件是否存在
    if not json_path.exists():
        print(f"错误: 找不到JSON文件 {json_path}")
        return None
    
    # 读取时间戳和标记
    with open(json_path, 'r', encoding='utf-8') as f:
        time_data = json.load(f)
    
    timestamps = time_data.get('timestamps', [])
    tokens = time_data.get('tokens', [])
    
    if not timestamps or not tokens:
        print("错误: JSON文件中没有找到时间戳或标记")
        return None
    
    # 创建LRC内容 - 为每个标记创建一个时间点
    lrc_lines = []
    
    # 添加文件头信息
    lrc_lines.append('[ti:自动转录字幕]')
    lrc_lines.append('[ar:CapsWriter-Offline]')
    lrc_lines.append('[al:自动生成]')
    lrc_lines.append('[by:CapsWriter-LRC生成器]')
    lrc_lines.append('')
    
    # 添加主要内容
    current_line = ''
    line_start_time = None
    current_time = 0
    char_threshold = 20  # 每行最多字符数，超过则换行
    
    for i, (token, timestamp) in enumerate(zip(tokens, timestamps)):
        # 如果是第一个字符或需要换行
        if current_line == '' or len(current_line) >= char_threshold:
            if current_line:  # 如果不是空行，写入当前行
                lrc_lines.append(f"{format_time_lrc(line_start_time)}{current_line}")
            current_line = token
            line_start_time = timestamp
        else:
            current_line += token
        
        current_time = timestamp
    
    # 添加最后一行
    if current_line:
        lrc_lines.append(f"{format_time_lrc(line_start_time)}{current_line}")
    
    # 写入LRC文件
    with open(lrc_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lrc_lines))
    
    return lrc_path 