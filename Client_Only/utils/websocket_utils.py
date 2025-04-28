#!/usr/bin/env python
# coding: utf-8

"""
WebSocket连接管理工具
"""
import websockets

from ..config import Config
from .cosmic import Cosmic, console

class ConnectionHandler:
    """连接异常处理类"""
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, e, exc_tb):
        if e is None:
            return True
        if isinstance(e, ConnectionRefusedError):
            console.print("[red]无法连接到服务器，请检查服务器地址和端口是否正确")
            return True
        elif isinstance(e, TimeoutError):
            console.print("[red]连接服务器超时")
            return True
        elif isinstance(e, Exception):
            console.print(f"[red]连接出错: {e}")
            return True
        return False

async def check_websocket() -> bool:
    """
    检查并建立WebSocket连接
    
    返回:
        bool: 连接是否成功
    """
    if Cosmic.websocket and not Cosmic.websocket.closed:
        return True
        
    for _ in range(3):  # 尝试3次
        with ConnectionHandler():
            server_url = f"ws://{Config.server_addr}:{Config.server_port}"
            Cosmic.websocket = await websockets.connect(server_url, max_size=None)
            Cosmic.log(f"[green]已连接到服务器: {server_url}")
            return True
    
    return False

async def close_websocket():
    """关闭WebSocket连接"""
    if Cosmic.websocket and not Cosmic.websocket.closed:
        await Cosmic.websocket.close()
        Cosmic.websocket = None
        Cosmic.log("[yellow]已关闭服务器连接") 