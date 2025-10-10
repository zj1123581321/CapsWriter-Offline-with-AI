import keyboard
from .client_cosmic import Cosmic, console
from ...config import ClientConfig as Config

import time
import asyncio
import sys
from threading import Event
from concurrent.futures import ThreadPoolExecutor
from .client_send_audio import send_audio
from ...utils.my_status import Status
from datetime import datetime


task = asyncio.Future()
status = Status('开始录音', spinner='point')
pool = ThreadPoolExecutor()
pressed = False
released = True
event = Event()
hold_start_time = None  # 记录长按模式下的按键开始时间


def shortcut_correct(e: keyboard.KeyboardEvent):
    # 在我的 Windows 电脑上，left ctrl 和 right ctrl 的 keycode 都是一样的，
    # keyboard 库按 keycode 判断触发
    # 即便设置 right ctrl 触发，在按下 left ctrl 时也会触发
    # 不过，虽然两个按键的 keycode 一样，但事件 e.name 是不一样的
    # 在这里加一个判断，如果 e.name 不是我们期待的按键，就返回
    key_expect = keyboard.normalize_name(Config.shortcut).replace('left ', '')
    key_actual = e.name.replace('left ', '')
    if key_expect != key_actual: return False
    return True


def launch_task():
    global task

    # 记录开始时间
    t1 = time.time()

    # 将开始标志放入队列
    asyncio.run_coroutine_threadsafe(
        Cosmic.queue_in.put({'type': 'begin', 'time': t1, 'data': None}),
        Cosmic.loop
    )

    # 通知录音线程可以向队列放数据了
    Cosmic.on = t1

    # 打印动画：正在录音
    status.start()
    
    # 输出录音开始日志，供进度指示器监测
    current_time = datetime.now().strftime("[%H:%M:%S]")
    console.print(f"{current_time} 开始录音")

    # 启动识别任务
    task = asyncio.run_coroutine_threadsafe(
        send_audio(),
        Cosmic.loop,
    )


def cancel_task():
    # 通知停止录音，关掉滚动条
    Cosmic.on = False
    status.stop()

    # 取消协程任务
    task.cancel()


def finish_task():
    global task

    # 通知停止录音，关掉滚动条
    Cosmic.on = False
    status.stop()
    
    # 输出录音结束日志，供进度指示器监测
    current_time = datetime.now().strftime("[%H:%M:%S]")
    console.print(f"{current_time} 录音结束")

    # 通知结束任务
    asyncio.run_coroutine_threadsafe(
        Cosmic.queue_in.put(
            {'type': 'finish',
             'time': time.time(),
             'data': None
             },
        ),
        Cosmic.loop
    )


# =================单击模式======================


def count_down(e: Event):
    """按下后，开始倒数"""
    time.sleep(Config.threshold)
    e.set()


def manage_task(e: Event):
    """
    通过检测 e 是否在 threshold 时间内被触发，判断是单击，还是长按
    进行下一步的动作
    """

    # 记录是否有任务
    on = Cosmic.on

    # 先运行任务
    if not on:
        launch_task()

    # 及时松开按键了，是单击
    if e.wait(timeout=Config.threshold * 0.8):
        # 如果有任务在运行，就结束任务
        if Cosmic.on and on:
            finish_task()

    # 没有及时松开按键，是长按
    else:
        # 就取消本栈启动的任务
        if not on:
            cancel_task()

        # 长按，发送按键
        keyboard.send(Config.shortcut)


def click_mode(e: keyboard.KeyboardEvent):
    global pressed, released, event

    if e.event_type == 'down' and released:
        pressed, released = True, False
        event = Event()
        pool.submit(count_down, event)
        pool.submit(manage_task, event)

    elif e.event_type == 'up' and pressed:
        pressed, released = False, True
        event.set()



# ======================长按模式==================================


def delayed_launch():
    """延迟启动任务，只有持续按下超过阈值才真正启动"""
    global hold_start_time

    # 等待 threshold 时间
    time.sleep(Config.threshold)

    # 检查是否仍在按住状态（通过检查 hold_start_time 是否被清除）
    if hold_start_time is not None:
        # 仍在按住，启动录音任务
        launch_task()


def hold_mode(e: keyboard.KeyboardEvent):
    """像对讲机一样，按下录音，松开停止

    改进：只有持续按下超过 threshold 阈值，才会显示录音状态和启动任务
    """
    global task, hold_start_time

    if e.event_type == 'down' and not Cosmic.on and hold_start_time is None:
        # 记录按键开始时间
        hold_start_time = time.time()

        # 在后台线程中延迟启动任务
        pool.submit(delayed_launch)

    elif e.event_type == 'up' and hold_start_time is not None:
        # 计算按键持续时间
        duration = time.time() - hold_start_time

        # 清除开始时间标记
        hold_start_time = None

        # 判断是否已经启动了任务
        if Cosmic.on:
            # 任务已启动，正常结束
            finish_task()

            # 松开快捷键后，再按一次，恢复 CapsLock 或 Shift 等按键的状态
            if Config.restore_key:
                time.sleep(0.01)
                keyboard.send(Config.shortcut)
        else:
            # 任务未启动（按键时间不足阈值），无需操作
            pass





# ==================== 绑定 handler ===============================


def hold_handler(e: keyboard.KeyboardEvent) -> None:

    # 验证按键名正确
    if not shortcut_correct(e):
        return

    # 长按模式
    hold_mode(e)


def click_handler(e: keyboard.KeyboardEvent) -> None:

    # 验证按键名正确
    if not shortcut_correct(e):
        return

    # 单击模式
    click_mode(e)


# ==================== 退出功能 ===============================

def exit_program():
    """优雅地退出程序"""
    console.print('\n\n[bold red]程序即将退出...[/bold red]')
    
    # 设置全局退出标志
    Cosmic.should_exit = True
    
    # 停止当前任务（如果有的话）
    if Cosmic.on:
        cancel_task()
    
    # 关闭音频流
    if hasattr(Cosmic, 'stream') and Cosmic.stream:
        try:
            Cosmic.stream.stop()
            Cosmic.stream.close()
        except:
            pass
    
    # 关闭WebSocket连接
    if hasattr(Cosmic, 'websocket') and Cosmic.websocket and Cosmic.websocket.close_code is None:
        try:
            asyncio.run_coroutine_threadsafe(
                Cosmic.websocket.close(),
                Cosmic.loop
            ).result(timeout=1.0)  # 等待最多1秒
        except:
            pass
    
    # 停止事件循环
    if hasattr(Cosmic, 'loop') and Cosmic.loop:
        try:
            Cosmic.loop.call_soon_threadsafe(Cosmic.loop.stop)
        except:
            pass
    
    console.print('[green]再见！[/green]')
    time.sleep(0.3)  # 给用户时间看到消息
    
    # 强制退出
    import os
    os._exit(0)


def exit_hotkey():
    """退出热键回调函数"""
    console.print('\n[yellow]检测到退出快捷键 Ctrl + Shift + C[/yellow]')
    exit_program()


def bond_shortcut():
    if Config.hold_mode:
        keyboard.hook_key(Config.shortcut, hold_handler, suppress=Config.suppress)
    else:
        # 单击模式，必须得阻塞快捷键
        # 收到长按时，再模拟发送按键
        keyboard.hook_key(Config.shortcut, click_handler, suppress=True)
    
    # 绑定退出快捷键 Ctrl + Shift + C
    try:
        keyboard.add_hotkey('ctrl+shift+c', exit_hotkey)
        console.print('[green]已注册退出快捷键: Ctrl + Shift + C[/green]')
    except Exception as e:
        console.print(f'[red]注册退出快捷键失败: {e}[/red]')
        # 备用方案：使用简单的 C 键检测
        keyboard.hook_key('c', lambda e: exit_hotkey() if e.event_type == 'down' and keyboard.is_pressed('ctrl') and keyboard.is_pressed('shift') else None, suppress=False)