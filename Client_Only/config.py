#!/usr/bin/env python
# coding: utf-8

"""
CapsWriter文件转录模块配置
"""

class Config:
    # 服务器连接配置
    server_addr = '100.89.110.76'  # 服务器地址
    server_port = 6016         # 服务器端口
    
    # 转录设置
    file_seg_duration = 25     # 转录文件时分段长度（秒）
    file_seg_overlap = 2       # 转录文件时分段重叠（秒）
    
    # 热词替换功能开关
    enable_hot_words = True    # 是否启用热词替换
    
    # 输出格式选项
    generate_txt = False        # 生成纯文本文件
    generate_merge_txt = False  # 生成合并文本（不分行）
    generate_srt = True        # 生成SRT字幕文件
    generate_lrc = True       # 生成LRC歌词/字幕文件
    generate_json = False       # 生成JSON详细信息
    
    # 日志设置
    verbose = True             # 是否显示详细日志
    
    @classmethod
    def update_server(cls, addr=None, port=None):
        """更新服务器连接信息"""
        if addr:
            cls.server_addr = addr
        if port:
            cls.server_port = port 