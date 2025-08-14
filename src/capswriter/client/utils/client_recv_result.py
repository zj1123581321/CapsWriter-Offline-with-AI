import asyncio
import json

import keyboard
import websockets
from ...config import ClientConfig as Config
from .client_cosmic import Cosmic, console
from .client_check_websocket import check_websocket
from .client_hot_sub import hot_sub
from .client_rename_audio import rename_audio
from .client_strip_punc import strip_punc
from .client_write_md import write_md
from .client_type_result import type_result
from .ai_enhancer import get_ai_enhancer


async def recv_result():
    # 检查是否需要退出
    if Cosmic.should_exit:
        return
        
    if not await check_websocket():
        return
    console.print('[green]连接成功\n')
    try:
        while not Cosmic.should_exit:
            # 接收消息
            message = await Cosmic.websocket.recv()
            message = json.loads(message)
            text = message['text']
            delay = message['time_complete'] - message['time_submit']

            # 如果非最终结果，继续等待
            if not message['is_final']:
                continue

            # 消除末尾标点
            text = strip_punc(text)

            # 热词替换
            text = hot_sub(text)

            # AI校对润色（如果启用）
            original_text = text
            if Config.ai_enhancement and text:
                try:
                    console.print('    [cyan]正在进行AI校对...')
                    enhancer = await get_ai_enhancer()
                    text = await enhancer.enhance_text(text)
                    if text != original_text:
                        console.print(f'    [blue]原文：{original_text}')
                        console.print(f'    [cyan]AI校对：{text}')
                    else:
                        console.print('    [cyan]AI校对完成（无修改）')
                except Exception as e:
                    console.print(f'    [red]AI校对失败: {str(e)}')
                    text = original_text

            # 打字
            await type_result(text)

            if Config.save_audio:
                # 重命名录音文件
                file_audio = rename_audio(message['task_id'], text, message['time_start'])

                # 记录写入 md 文件
                write_md(text, message['time_start'], file_audio)

            # 控制台输出
            console.print(f'    转录时延：{delay:.2f}s')
            console.print(f'    识别结果：[green]{text}')
            console.line()

    except websockets.ConnectionClosedError:
        console.print('[red]连接断开\n')
    except websockets.ConnectionClosedOK:
        console.print('[red]连接断开\n')
    except Exception as e:
        print(e)
    finally:
        return
