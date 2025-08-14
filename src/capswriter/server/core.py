import os
import sys
import asyncio
from multiprocessing import Process, Manager
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

    # 跨进程列表，用于保存 socket 的 id，用于让识别进程查看连接是否中断
    Cosmic.sockets_id = Manager().list()

    # 负责识别的子进程
    recognize_process = Process(target=init_recognizer,
                                args=(Cosmic.queue_in,
                                      Cosmic.queue_out,
                                      Cosmic.sockets_id),
                                daemon=True)
    recognize_process.start()
    
    # 等待识别器初始化结果
    init_result = Cosmic.queue_out.get()
    if init_result is None:
        console.print('[red]服务端初始化失败，请检查依赖安装[/red]')
        recognize_process.terminate()
        return
        
    console.rule('[green3]开始服务')
    console.line()

    # 清空物理内存工作集
    if system() == 'Windows':
        empty_current_working_set()

    # 负责接收客户端数据的 coroutine
    recv = websockets.serve(ws_recv,
                            Config.addr,
                            Config.port,
                            subprotocols=["binary"],
                            max_size=None)

    # 负责发送结果的 coroutine
    send = ws_send()
    await asyncio.gather(recv, send)


def init():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:           # Ctrl-C 停止
        console.print('\n再见！')
    except OSError as e:                # 端口占用
        console.print(f'出错了：{e}', style='bright_red'); console.input('...')
    except Exception as e:
        print(e)
    finally:
        Cosmic.queue_out.put(None)
        sys.exit(0)
        # os._exit(0)
     
        
if __name__ == "__main__":
    init()
