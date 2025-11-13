"""
并发测试客户端
用于同时向 Server 发送多个音频文件，测试多进程处理能力

功能：
1. 同时发送多个音频文件
2. 记录每个文件的处理时间
3. 统计并发性能指标
"""

import asyncio
import base64
import json
import sys
import time
import uuid
from pathlib import Path
from typing import List, Dict
import subprocess

import websockets
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

console = Console()


class TranscriptionResult:
    """转录结果数据类"""
    def __init__(self, file_path: Path, task_id: str):
        self.file_path = file_path
        self.task_id = task_id
        self.audio_duration = 0
        self.time_start = 0
        self.time_complete = 0
        self.text = ""
        self.success = False

    @property
    def process_duration(self):
        """处理耗时"""
        return self.time_complete - self.time_start if self.time_complete else 0

    @property
    def rtf(self):
        """Real-Time Factor (处理时间/音频时长)"""
        if self.audio_duration > 0:
            return self.process_duration / self.audio_duration
        return 0


async def send_audio_file(websocket, file_path: Path, task_id: str) -> TranscriptionResult:
    """
    发送单个音频文件到服务端

    Args:
        websocket: WebSocket 连接
        file_path: 音频文件路径
        task_id: 任务ID

    Returns:
        TranscriptionResult: 转录结果
    """
    result = TranscriptionResult(file_path, task_id)

    # 使用 ffmpeg 提取音频数据
    ffmpeg_cmd = [
        "ffmpeg",
        "-i", str(file_path),
        "-f", "f32le",
        "-ac", "1",
        "-ar", "16000",
        "-",
    ]

    try:
        process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )
        data = process.stdout.read()
        result.audio_duration = len(data) / 4 / 16000

        # 构建分段消息，发送给服务端
        result.time_start = time.time()
        offset = 0

        while True:
            chunk_end = offset + 16000 * 4 * 60  # 60秒分段
            is_final = False if chunk_end < len(data) else True

            message = {
                'task_id': task_id,
                'seg_duration': 25,  # 分段长度
                'seg_overlap': 2,    # 分段重叠
                'is_final': is_final,
                'time_start': result.time_start,
                'time_frame': time.time(),
                'source': 'file',
                'data': base64.b64encode(data[offset: chunk_end]).decode('utf-8'),
            }

            await websocket.send(json.dumps(message))
            offset = chunk_end

            if is_final:
                break

        return result

    except Exception as e:
        console.print(f"[red]发送文件 {file_path.name} 失败: {e}")
        return result


async def receive_result(websocket, result: TranscriptionResult):
    """
    接收单个文件的转录结果

    Args:
        websocket: WebSocket 连接
        result: 转录结果对象（会被修改）
    """
    try:
        async for message in websocket:
            message_data = json.loads(message)

            # 检查是否是当前任务的结果
            if message_data['task_id'] == result.task_id:
                if message_data['is_final']:
                    result.text = message_data['text']
                    result.time_complete = message_data['time_complete']
                    result.success = True
                    break

    except Exception as e:
        console.print(f"[red]接收结果失败: {e}")


async def process_single_file(server_url: str, file_path: Path) -> TranscriptionResult:
    """
    处理单个文件（独立连接）

    Args:
        server_url: 服务器地址
        file_path: 音频文件路径

    Returns:
        TranscriptionResult: 转录结果
    """
    task_id = str(uuid.uuid4())

    try:
        async with websockets.connect(server_url, max_size=None) as websocket:
            # 发送文件
            result = await send_audio_file(websocket, file_path, task_id)

            # 接收结果
            await receive_result(websocket, result)

            return result

    except Exception as e:
        console.print(f"[red]处理文件 {file_path.name} 时出错: {e}")
        result = TranscriptionResult(file_path, task_id)
        return result


async def run_concurrent_test(
    server_url: str,
    files: List[Path],
    show_progress: bool = True
) -> List[TranscriptionResult]:
    """
    运行并发测试

    Args:
        server_url: 服务器地址
        files: 要处理的文件列表
        show_progress: 是否显示进度条

    Returns:
        List[TranscriptionResult]: 所有文件的转录结果
    """
    console.print(f"\n[cyan]开始并发测试：同时处理 {len(files)} 个文件...[/cyan]\n")

    # 记录测试开始时间
    test_start_time = time.time()

    # 创建任务列表
    tasks = [process_single_file(server_url, file_path) for file_path in files]

    # 并发执行
    if show_progress:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            task = progress.add_task("[cyan]处理中...", total=len(files))
            results = await asyncio.gather(*tasks)
            progress.update(task, completed=len(files))
    else:
        results = await asyncio.gather(*tasks)

    # 计算总耗时
    test_duration = time.time() - test_start_time

    # 打印结果
    print_test_results(results, test_duration)

    return results


def print_test_results(results: List[TranscriptionResult], total_duration: float):
    """
    打印测试结果统计表格

    Args:
        results: 转录结果列表
        total_duration: 总耗时
    """
    console.print("\n")
    console.rule("[bold green]测试结果", style="green")
    console.print()

    # 创建结果表格
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("文件名", style="cyan", width=20)
    table.add_column("音频时长(s)", justify="right")
    table.add_column("处理时长(s)", justify="right")
    table.add_column("RTF", justify="right")
    table.add_column("状态", justify="center")
    table.add_column("识别结果预览", width=30)

    success_count = 0
    total_audio_duration = 0
    total_process_duration = 0

    for result in results:
        if result.success:
            success_count += 1
            total_audio_duration += result.audio_duration
            total_process_duration += result.process_duration

            status = "[green]✓ 成功"
            rtf_str = f"{result.rtf:.2f}"
            text_preview = result.text[:30] + "..." if len(result.text) > 30 else result.text
        else:
            status = "[red]✗ 失败"
            rtf_str = "-"
            text_preview = "-"

        table.add_row(
            result.file_path.name,
            f"{result.audio_duration:.2f}",
            f"{result.process_duration:.2f}",
            rtf_str,
            status,
            text_preview
        )

    console.print(table)
    console.print()

    # 统计信息
    stats_table = Table(show_header=True, header_style="bold yellow")
    stats_table.add_column("指标", style="cyan", width=25)
    stats_table.add_column("数值", justify="right", style="green")

    stats_table.add_row("并发文件数", str(len(results)))
    stats_table.add_row("成功数量", str(success_count))
    stats_table.add_row("失败数量", str(len(results) - success_count))
    stats_table.add_row("总音频时长", f"{total_audio_duration:.2f}s")
    stats_table.add_row("总测试耗时", f"{total_duration:.2f}s")

    if success_count > 0:
        avg_rtf = total_process_duration / total_audio_duration if total_audio_duration > 0 else 0
        speedup = total_process_duration / total_duration if total_duration > 0 else 0

        stats_table.add_row("平均 RTF", f"{avg_rtf:.2f}")
        stats_table.add_row("并发加速比", f"{speedup:.2f}x")

        if speedup > 1.5:
            speedup_status = "[green]✓ 并发有效"
        elif speedup > 1.1:
            speedup_status = "[yellow]△ 部分有效"
        else:
            speedup_status = "[red]✗ 并发无效"

        stats_table.add_row("并发效果", speedup_status)

    console.print(stats_table)
    console.print()


async def main():
    """主函数"""
    # 配置
    SERVER_ADDR = "127.0.0.1"
    SERVER_PORT = "6016"
    server_url = f"ws://{SERVER_ADDR}:{SERVER_PORT}"

    # 测试文件路径
    sample_dir = Path(__file__).parent.parent.parent / "ref_codes" / "samples"
    test_files = list(sample_dir.glob("*.mp3"))

    if not test_files:
        console.print("[red]错误：未找到测试文件")
        console.print(f"[yellow]请确保以下目录存在音频文件：{sample_dir}")
        return

    console.print(f"[green]找到 {len(test_files)} 个测试文件")
    for f in test_files:
        console.print(f"  - {f.name}")

    # 检查连接
    console.print(f"\n[cyan]正在连接服务器 {server_url}...[/cyan]")
    try:
        async with websockets.connect(server_url) as ws:
            console.print("[green]✓ 服务器连接成功[/green]")
    except Exception as e:
        console.print(f"[red]✗ 无法连接到服务器: {e}[/red]")
        console.print("[yellow]请确保服务端已启动[/yellow]")
        return

    # 运行并发测试
    results = await run_concurrent_test(server_url, test_files)

    console.print("\n[bold green]测试完成！[/bold green]\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]测试被用户中断[/yellow]")
        sys.exit(0)
