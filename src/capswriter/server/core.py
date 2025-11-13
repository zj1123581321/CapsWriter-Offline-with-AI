import os
import sys
import asyncio
from multiprocessing import Process, Manager, Queue
from typing import List
from platform import system

import websockets
from ..config import ServerConfig as Config
from .utils.server_cosmic import Cosmic, console
from .utils.server_check_model import check_model
from .utils.server_ws_recv import ws_recv
from .utils.server_ws_send import ws_send
from .utils.server_init_recognizer import init_recognizer
from ..utils.empty_working_set import empty_current_working_set

# 获取项目根目录，确保相对路径正确
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
os.chdir(BASE_DIR)

async def main():

    # 检查模型文件
    check_model()

    console.line(2)
    console.rule('[bold #d55252]CapsWriter Offline Server'); console.line()
    console.print(f'项目地址：[cyan underline]https://github.com/HaujetZhao/CapsWriter-Offline', end='\n\n')
    console.print(f'当前基文件夹：[cyan underline]{BASE_DIR}', end='\n\n')
    console.print(f'绑定的服务地址：[cyan underline]{Config.addr}:{Config.port}', end='\n\n')

    # ========== 多进程支持：开始 ==========

    # 获取进程数配置（向后兼容旧配置）
    num_workers = max(1, getattr(Config, 'worker_processes', 1))

    # 显示进程模式
    if num_workers > 1:
        console.print(f'[yellow]⚡ 多进程模式：启动 {num_workers} 个识别进程[/yellow]', end='\n\n')
    else:
        console.print(f'[cyan]单进程模式[/cyan]', end='\n\n')

    # 创建跨进程通信组件
    manager = Manager()
    Cosmic.sockets_id = manager.list()  # 跨进程共享的 socket ID 列表
    Cosmic.queue_out = manager.Queue()  # ⚠️ 关键：使用 Manager().Queue() 而非普通 Queue()
    Cosmic.queues_in = [manager.Queue() for _ in range(num_workers)]  # 每个进程一个输入队列

    # 创建任务分配器（单例）
    from .utils.task_dispatcher import TaskDispatcher
    Cosmic.dispatcher = TaskDispatcher(Cosmic.queues_in)

    # 创建识别进程池
    recognize_processes: List[Process] = []

    for i in range(num_workers):
        # 为每个进程创建专属的输入队列
        queue_in = Cosmic.queues_in[i]

        # 创建进程
        process = Process(
            target=init_recognizer,
            args=(queue_in, Cosmic.queue_out, Cosmic.sockets_id),
            daemon=True,
            name=f'RecognizerWorker-{i}'
        )
        process.start()
        recognize_processes.append(process)

        # 显示进度（仅多进程模式）
        if num_workers > 1:
            console.print(f'  启动进程 {i+1}/{num_workers}...', end='\r')

        # 等待该进程初始化完成
        init_result = Cosmic.queue_out.get()
        if init_result is None:
            console.print(f'[red]进程 {i+1} 初始化失败，正在终止所有进程...[/red]')
            # 终止已启动的所有进程
            for p in recognize_processes:
                if p.is_alive():
                    p.terminate()
            return

        # 显示完成状态（仅多进程模式）
        if num_workers > 1:
            console.print(f'  ✓ 进程 {i+1}/{num_workers} 初始化完成')

    # 记录进程池（用于后续管理，如优雅关闭）
    Cosmic.recognize_processes = recognize_processes

    # ========== 多进程支持：结束 ==========

    console.line()
    console.rule('[green3]开始服务')
    console.line()

    # 清空物理内存工作集
    if system() == 'Windows':
        empty_current_working_set()

    # 负责接收客户端数据的 coroutine
    recv = websockets.serve(ws_recv,
                            Config.addr,
                            Config.port,
                            # subprotocols=["binary"],
                            max_size=None)

    # 负责发送结果的 coroutine
    send = ws_send()
    await asyncio.gather(recv, send)


def init():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:           # Ctrl-C 停止
        console.print('\n[yellow]正在关闭...[/yellow]')
    except OSError as e:                # 端口占用
        console.print(f'出错了：{e}', style='bright_red'); console.input('...')
    except Exception as e:
        console.print(f'异常：{e}', style='bright_red')
    finally:
        # 通知识别进程退出
        if Cosmic.queue_out is not None:
            Cosmic.queue_out.put(None)

        # 终止所有识别进程（如果有）
        if hasattr(Cosmic, 'recognize_processes'):
            for process in Cosmic.recognize_processes:
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=2)  # 等待最多2秒

        console.print('[green]再见！[/green]')
        sys.exit(0)
        # os._exit(0)
     
        
if __name__ == "__main__":
    init()
