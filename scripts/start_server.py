# coding: utf-8


'''
这个文件仅仅是为了 PyInstaller 打包用
'''

import sys
import os
from multiprocessing import freeze_support

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import src.capswriter.server.core as core_server


if __name__ == '__main__':
    freeze_support()
    core_server.init()