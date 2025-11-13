"""
多进程版本 Server 核心模块（测试版）
基于原 core.py 改造，支持多识别进程

测试目标：
1. 验证多进程架构的可行性
2. 测试任务分配机制
3. 监控资源占用情况
"""

import os
import sys
import asyncio
from multiprocessing import Process, Manager
from platform import system

# 获取项目根目录，添加到 Python 路径
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(BASE_DIR, 'src'))
os.chdir(BASE_DIR)

import websockets
from capswriter.config import ServerConfig as Config
from capswriter.server.utils.server_cosmic import Cosmic, console
from capswriter.server.utils.server_check_model import check_model
from capswriter.server.utils.server_ws_recv import ws_recv
from capswriter.server.utils.server_ws_send import ws_send
from capswriter.server.utils.server_init_recognizer import init_recognizer
from capswriter.utils.empty_working_set import empty_current_working_set


# ========== 新增配置 ==========
class MultiProcessConfig:
    """多进程配置"""
    worker_processes = 2  # 识别进程数（测试先用2个）
    enable_monitoring = True  # 是否启用资源监控
    max_queue_size = 100  # 任务队列最大长度


async def main():
    """主函数（多进程版本）"""

    # 检查模型文件
    check_model()

    console.line(2)
    console.rule('[bold #d55252]CapsWriter Offline Server (Multi-Process Test)')
    console.line()
    console.print(f'项目地址：[cyan underline]https://github.com/HaujetZhao/CapsWriter-Offline', end='\n\n')
    console.print(f'当前基文件夹：[cyan underline]{BASE_DIR}', end='\n\n')
    console.print(f'绑定的服务地址：[cyan underline]{Config.addr}:{Config.port}', end='\n\n')
    console.print(f'[yellow]🔧 多进程模式：{MultiProcessConfig.worker_processes} 个识别进程[/yellow]', end='\n\n')

    # 跨进程列表，用于保存 socket 的 id
    Cosmic.sockets_id = Manager().list()

    # ========== 创建多个识别子进程 ==========
    recognize_processes = []

    console.print(f'[cyan]正在启动 {MultiProcessConfig.worker_processes} 个识别进程...[/cyan]')

    for i in range(MultiProcessConfig.worker_processes):
        console.print(f'  启动进程 {i+1}...', end='\r')

        # 创建识别进程
        process = Process(
            target=init_recognizer,
            args=(Cosmic.queue_in, Cosmic.queue_out, Cosmic.sockets_id),
            daemon=True,
            name=f'RecognizerWorker-{i+1}'
        )
        process.start()
        recognize_processes.append(process)

        # 等待该进程初始化完成
        init_result = Cosmic.queue_out.get()
        if init_result is None:
            console.print(f'[red]进程 {i+1} 初始化失败，正在终止所有进程...[/red]')
            for p in recognize_processes:
                p.terminate()
            return

        console.print(f'  ✅ 进程 {i+1} 初始化完成')

    console.line()
    console.rule('[green3]所有识别进程已就绪，开始服务')
    console.line()

    # 清空物理内存工作集
    if system() == 'Windows':
        empty_current_working_set()

    # 负责接收客户端数据的 coroutine
    recv = websockets.serve(
        ws_recv,
        Config.addr,
        Config.port,
        max_size=None
    )

    # 负责发送结果的 coroutine
    send = ws_send()

    await asyncio.gather(recv, send)


def init():
    """初始化入口"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print('\n再见！')
    except OSError as e:
        console.print(f'出错了：{e}', style='bright_red')
        console.input('...')
    except Exception as e:
        console.print(f'异常：{e}', style='bright_red')
        import traceback
        traceback.print_exc()
    finally:
        Cosmic.queue_out.put(None)
        sys.exit(0)


if __name__ == "__main__":
    init()
