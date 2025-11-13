import sys
from pathlib import Path
from multiprocessing import Queue
from typing import Dict, List
import websockets
from rich.console import Console 
console = Console(highlight=False)





class Cosmic:
    sockets: Dict[str, websockets.WebSocketClientProtocol] = {}
    sockets_id: List = None
    queues_in: List[Queue] = []  # 改为队列列表（每个进程一个）
    queue_out: Queue = None      # ⚠️ 改为 None，稍后用 Manager().Queue() 创建
    dispatcher: 'TaskDispatcher' = None  # 任务分配器（单例）
