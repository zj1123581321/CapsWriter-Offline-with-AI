"""
资源监控工具
实时监控 Server 进程的 CPU、内存使用情况

功能：
1. 监控主进程和所有子进程的资源占用
2. 实时显示资源使用图表
3. 记录监控日志用于后续分析
"""

import os
import sys
import psutil
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import argparse

# 确保可以导入 rich（项目依赖）
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text

console = Console()


class ProcessMonitor:
    """进程监控器"""

    def __init__(self, process_name: str = "python", interval: float = 1.0):
        """
        初始化监控器

        Args:
            process_name: 要监控的进程名
            interval: 监控间隔（秒）
        """
        self.process_name = process_name
        self.interval = interval
        self.history: List[Dict] = []
        self.max_history = 60  # 保存最近60次记录

    def find_server_processes(self) -> List[psutil.Process]:
        """
        查找所有 CapsWriter Server 相关进程

        Returns:
            List[psutil.Process]: 进程列表
        """
        processes = []

        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline and any('capswriter' in arg.lower() for arg in cmdline):
                    # 检查是否是 server 进程
                    if any('server' in arg.lower() for arg in cmdline):
                        processes.append(proc)
                    # 或者检查是否包含 test_core_multiprocess
                    elif any('test_core_multiprocess' in arg for arg in cmdline):
                        processes.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return processes

    def get_process_info(self, process: psutil.Process) -> Dict:
        """
        获取进程信息

        Args:
            process: 进程对象

        Returns:
            Dict: 进程信息
        """
        try:
            # 获取进程的子进程
            children = process.children(recursive=True)

            # 计算总资源占用（包括子进程）
            total_cpu = process.cpu_percent(interval=0.1)
            total_memory = process.memory_info().rss

            for child in children:
                try:
                    total_cpu += child.cpu_percent(interval=0.1)
                    total_memory += child.memory_info().rss
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            return {
                'pid': process.pid,
                'name': process.name(),
                'num_children': len(children),
                'cpu_percent': total_cpu,
                'memory_mb': total_memory / 1024 / 1024,
                'memory_percent': total_memory / psutil.virtual_memory().total * 100,
                'children': [
                    {
                        'pid': child.pid,
                        'name': child.name(),
                        'cpu_percent': child.cpu_percent(interval=0.1),
                        'memory_mb': child.memory_info().rss / 1024 / 1024,
                    }
                    for child in children
                ],
                'timestamp': datetime.now()
            }

        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            return None

    def create_monitor_table(self, processes_info: List[Dict]) -> Table:
        """
        创建监控表格

        Args:
            processes_info: 进程信息列表

        Returns:
            Table: Rich 表格对象
        """
        table = Table(
            title="CapsWriter Server 资源监控",
            show_header=True,
            header_style="bold magenta"
        )

        table.add_column("进程", style="cyan", width=20)
        table.add_column("PID", justify="right", width=8)
        table.add_column("子进程数", justify="right", width=10)
        table.add_column("CPU %", justify="right", width=10)
        table.add_column("内存 (MB)", justify="right", width=12)
        table.add_column("内存 %", justify="right", width=10)

        if not processes_info:
            table.add_row(
                "[red]未找到进程",
                "-", "-", "-", "-", "-"
            )
            return table

        # 主进程信息
        for info in processes_info:
            if info:
                cpu_style = "red" if info['cpu_percent'] > 80 else "yellow" if info['cpu_percent'] > 50 else "green"
                mem_style = "red" if info['memory_percent'] > 80 else "yellow" if info['memory_percent'] > 50 else "green"

                table.add_row(
                    f"主进程 ({info['name']})",
                    str(info['pid']),
                    str(info['num_children']),
                    f"[{cpu_style}]{info['cpu_percent']:.1f}[/{cpu_style}]",
                    f"[{mem_style}]{info['memory_mb']:.1f}[/{mem_style}]",
                    f"[{mem_style}]{info['memory_percent']:.1f}[/{mem_style}]"
                )

                # 子进程信息
                for child in info['children']:
                    table.add_row(
                        f"  └─ {child['name']}",
                        str(child['pid']),
                        "-",
                        f"{child['cpu_percent']:.1f}",
                        f"{child['memory_mb']:.1f}",
                        "-"
                    )

        return table

    def create_summary_panel(self, processes_info: List[Dict]) -> Panel:
        """
        创建摘要面板

        Args:
            processes_info: 进程信息列表

        Returns:
            Panel: Rich 面板对象
        """
        if not processes_info or not any(processes_info):
            text = Text("❌ 未检测到 CapsWriter Server 进程\n", style="red")
            text.append("请确保服务端正在运行", style="yellow")
            return Panel(text, title="系统状态", border_style="red")

        # 计算总资源
        total_cpu = sum(info['cpu_percent'] for info in processes_info if info)
        total_memory = sum(info['memory_mb'] for info in processes_info if info)
        total_processes = sum(1 + info['num_children'] for info in processes_info if info)

        # 系统总内存
        sys_memory = psutil.virtual_memory()
        sys_cpu = psutil.cpu_percent(interval=0.1)

        text = Text()
        text.append("📊 资源占用总览\n\n", style="bold cyan")

        text.append(f"  进程总数: ", style="white")
        text.append(f"{total_processes}\n", style="bold green")

        text.append(f"  总 CPU: ", style="white")
        cpu_style = "red" if total_cpu > 300 else "yellow" if total_cpu > 200 else "green"
        text.append(f"{total_cpu:.1f}%\n", style=f"bold {cpu_style}")

        text.append(f"  总内存: ", style="white")
        mem_style = "red" if total_memory > 6000 else "yellow" if total_memory > 4000 else "green"
        text.append(f"{total_memory:.1f} MB\n", style=f"bold {mem_style}")

        text.append(f"\n💻 系统状态\n\n", style="bold cyan")
        text.append(f"  系统 CPU: ", style="white")
        text.append(f"{sys_cpu:.1f}%\n", style="green")

        text.append(f"  系统内存: ", style="white")
        text.append(
            f"{sys_memory.used / 1024 / 1024 / 1024:.1f} GB / {sys_memory.total / 1024 / 1024 / 1024:.1f} GB "
            f"({sys_memory.percent:.1f}%)\n",
            style="green"
        )

        return Panel(text, title="监控摘要", border_style="cyan")

    def run_monitor(self, log_file: Path = None):
        """
        运行监控

        Args:
            log_file: 日志文件路径（可选）
        """
        console.print("\n[cyan]开始监控 CapsWriter Server 进程...[/cyan]")
        console.print("[yellow]按 Ctrl+C 停止监控[/yellow]\n")

        # 打开日志文件
        log_fp = None
        if log_file:
            log_fp = open(log_file, 'w', encoding='utf-8')
            log_fp.write("timestamp,pid,name,num_children,cpu_percent,memory_mb,memory_percent\n")
            console.print(f"[green]日志将保存到: {log_file}[/green]\n")

        try:
            with Live(console=console, refresh_per_second=1) as live:
                while True:
                    # 查找进程
                    server_processes = self.find_server_processes()

                    # 获取进程信息
                    processes_info = [
                        self.get_process_info(proc)
                        for proc in server_processes
                    ]

                    # 创建显示布局
                    layout = Layout()
                    layout.split_column(
                        Layout(self.create_summary_panel(processes_info), size=12),
                        Layout(self.create_monitor_table(processes_info))
                    )

                    # 更新显示
                    live.update(layout)

                    # 记录到日志
                    if log_fp:
                        for info in processes_info:
                            if info:
                                log_fp.write(
                                    f"{info['timestamp'].isoformat()},"
                                    f"{info['pid']},"
                                    f"{info['name']},"
                                    f"{info['num_children']},"
                                    f"{info['cpu_percent']:.2f},"
                                    f"{info['memory_mb']:.2f},"
                                    f"{info['memory_percent']:.2f}\n"
                                )
                                log_fp.flush()

                    # 等待
                    time.sleep(self.interval)

        except KeyboardInterrupt:
            console.print("\n\n[yellow]监控已停止[/yellow]\n")

        finally:
            if log_fp:
                log_fp.close()
                console.print(f"[green]日志已保存到: {log_file}[/green]\n")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="监控 CapsWriter Server 进程资源占用"
    )
    parser.add_argument(
        '--interval',
        type=float,
        default=1.0,
        help='监控间隔（秒），默认 1.0'
    )
    parser.add_argument(
        '--log',
        type=str,
        default=None,
        help='日志文件路径（可选）'
    )

    args = parser.parse_args()

    # 创建日志路径
    log_file = None
    if args.log:
        log_file = Path(args.log)
    else:
        # 默认日志路径
        log_dir = Path(__file__).parent / 'logs'
        log_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = log_dir / f'resource_monitor_{timestamp}.csv'

    # 创建监控器
    monitor = ProcessMonitor(interval=args.interval)

    # 运行监控
    monitor.run_monitor(log_file)


if __name__ == "__main__":
    main()
