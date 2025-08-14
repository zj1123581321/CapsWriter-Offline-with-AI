# coding: utf-8


"""
这个文件仅仅是为了 PyInstaller 打包用
"""

import sys
import os
import typer

# 获取当前脚本的目录
if hasattr(sys, '_MEIPASS'):
    # PyInstaller 打包后的运行环境
    base_path = sys._MEIPASS
    # src目录在internal/src，需要添加internal目录到路径
    internal_path = os.path.join(os.path.dirname(sys.executable), 'internal')
    sys.path.insert(0, internal_path)
else:
    # 开发环境
    base_path = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.join(base_path, '..')
    # 添加项目根目录到路径
    sys.path.insert(0, project_root)

try:
    from src.capswriter.client.core import init_file, init_mic
except ImportError:
    # 如果无法导入，尝试直接导入
    try:
        import capswriter.client.core as core
        init_file = core.init_file
        init_mic = core.init_mic
    except ImportError:
        print("错误：无法导入客户端核心模块，请检查依赖是否完整")
        sys.exit(1)

if __name__ == "__main__":
    # 如果参数传入文件，那就转录文件
    # 如果没有多余参数，就从麦克风输入
    if sys.argv[1:]:
        typer.run(init_file)
    else:
        init_mic()