"""
一键测试脚本
自动运行完整的多进程测试流程

使用方法：
    python tests/multiprocess/run_test.py [--mode baseline|multiprocess|compare]

模式说明：
    baseline     - 仅运行基准测试（单进程）
    multiprocess - 仅运行多进程测试
    compare      - 完整对比测试（默认）
"""

import argparse
import asyncio
import sys
import time
from pathlib import Path
from typing import Dict

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()


def print_banner():
    """打印欢迎横幅"""
    console.print()
    console.rule("[bold cyan]CapsWriter 多进程测试套件", style="cyan")
    console.print()


def print_test_instructions():
    """打印测试说明"""
    panel = Panel(
        "[yellow]测试步骤：[/yellow]\n\n"
        "1. 本脚本将引导你完成测试\n"
        "2. 请按照提示在不同终端运行命令\n"
        "3. 确保每个步骤完成后再继续\n\n"
        "[cyan]需要准备 3 个终端窗口[/cyan]",
        title="📋 测试说明",
        border_style="yellow"
    )
    console.print(panel)
    console.print()


def print_step(step_num: int, title: str, description: str, commands: list = None):
    """
    打印测试步骤

    Args:
        step_num: 步骤编号
        title: 步骤标题
        description: 步骤描述
        commands: 要执行的命令列表
    """
    console.print()
    console.rule(f"[bold cyan]步骤 {step_num}: {title}", style="cyan")
    console.print()
    console.print(f"[white]{description}[/white]\n")

    if commands:
        for i, cmd in enumerate(commands, 1):
            console.print(f"[yellow]终端 {cmd['terminal']}:[/yellow]")
            console.print(f"[green]$ {cmd['command']}[/green]\n")


def wait_for_user(message: str = "完成后按回车继续"):
    """等待用户确认"""
    console.print(f"[bold yellow]⏸  {message}...[/bold yellow]")
    input()
    console.print("[green]✓ 继续[/green]\n")


async def run_baseline_test():
    """运行基准测试流程"""
    console.print("\n[bold cyan]═══════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]    基准测试（单进程模式）[/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════[/bold cyan]\n")

    # 步骤 1：启动原版 Server
    print_step(
        1,
        "启动原版 Server",
        "在终端 1 中启动单进程版本的 Server",
        [{"terminal": 1, "command": "python -m capswriter.server.core"}]
    )
    wait_for_user("等待 Server 启动完成，看到 '开始服务' 提示后")

    # 步骤 2：启动资源监控
    print_step(
        2,
        "启动资源监控",
        "在终端 2 中启动资源监控工具",
        [{"terminal": 2, "command": "python tests/multiprocess/monitor_resources.py"}]
    )
    wait_for_user("确认监控工具正常运行后")

    # 步骤 3：运行测试客户端
    print_step(
        3,
        "运行测试客户端",
        "在终端 3 中运行并发测试客户端",
        [{"terminal": 3, "command": "python tests/multiprocess/test_concurrent_client.py"}]
    )

    console.print("[bold yellow]测试正在运行，请等待完成...[/bold yellow]\n")
    wait_for_user("测试完成后")

    # 步骤 4：记录结果
    print_step(
        4,
        "记录测试结果",
        "请记录以下数据，稍后用于对比"
    )

    results = {}
    console.print("[cyan]请输入基准测试结果：[/cyan]\n")

    results['file1_duration'] = float(input("文件1处理时长 (秒): ") or "0")
    results['file2_duration'] = float(input("文件2处理时长 (秒): ") or "0")
    results['total_duration'] = float(input("总测试耗时 (秒): ") or "0")
    results['peak_memory'] = float(input("峰值内存占用 (MB): ") or "0")
    results['avg_cpu'] = float(input("平均CPU占用 (%): ") or "0")

    console.print("\n[green]✓ 基准测试数据已记录[/green]\n")

    # 步骤 5：停止所有进程
    print_step(
        5,
        "停止所有进程",
        "在各个终端中按 Ctrl+C 停止运行的程序"
    )
    wait_for_user("所有进程停止后")

    return results


async def run_multiprocess_test():
    """运行多进程测试流程"""
    console.print("\n[bold cyan]═══════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]    并发测试（多进程模式）[/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════[/bold cyan]\n")

    # 步骤 1：启动多进程 Server
    print_step(
        1,
        "启动多进程 Server",
        "在终端 1 中启动多进程版本的 Server",
        [{"terminal": 1, "command": "python tests/multiprocess/test_core_multiprocess.py"}]
    )
    console.print("[yellow]注意观察启动日志，应该看到：[/yellow]")
    console.print("[white]  ✅ 进程 1 初始化完成[/white]")
    console.print("[white]  ✅ 进程 2 初始化完成[/white]\n")
    wait_for_user("等待所有识别进程初始化完成后")

    # 步骤 2：启动资源监控
    print_step(
        2,
        "启动资源监控",
        "在终端 2 中启动资源监控工具（使用更高频率）",
        [{"terminal": 2, "command": "python tests/multiprocess/monitor_resources.py --interval 0.5"}]
    )
    console.print("[yellow]关键观察指标：[/yellow]")
    console.print("[white]  - 进程总数：应该是 3 个（1主+2子）[/white]")
    console.print("[white]  - 总内存：预期 3-6 GB[/white]")
    console.print("[white]  - CPU：并发时多个进程同时高占用[/white]\n")
    wait_for_user("确认监控工具正常显示后")

    # 步骤 3：运行测试客户端
    print_step(
        3,
        "运行测试客户端",
        "在终端 3 中运行并发测试客户端",
        [{"terminal": 3, "command": "python tests/multiprocess/test_concurrent_client.py"}]
    )

    console.print("[bold yellow]测试正在运行，请观察：[/bold yellow]")
    console.print("[white]  - 终端 2 的资源监控变化[/white]")
    console.print("[white]  - 两个文件应该同时处理[/white]\n")
    wait_for_user("测试完成后")

    # 步骤 4：记录结果
    print_step(
        4,
        "记录测试结果",
        "请记录以下数据"
    )

    results = {}
    console.print("[cyan]请输入多进程测试结果：[/cyan]\n")

    results['file1_duration'] = float(input("文件1处理时长 (秒): ") or "0")
    results['file2_duration'] = float(input("文件2处理时长 (秒): ") or "0")
    results['total_duration'] = float(input("总测试耗时 (秒): ") or "0")
    results['speedup'] = float(input("并发加速比: ") or "0")
    results['peak_memory'] = float(input("峰值内存占用 (MB): ") or "0")
    results['avg_cpu'] = float(input("平均CPU占用 (%): ") or "0")

    console.print("\n[green]✓ 多进程测试数据已记录[/green]\n")

    # 步骤 5：停止所有进程
    print_step(
        5,
        "停止所有进程",
        "在各个终端中按 Ctrl+C 停止运行的程序"
    )
    wait_for_user("所有进程停止后")

    return results


def compare_results(baseline: Dict, multiprocess: Dict):
    """
    对比测试结果

    Args:
        baseline: 基准测试结果
        multiprocess: 多进程测试结果
    """
    console.print("\n")
    console.rule("[bold green]测试结果对比", style="green")
    console.print("\n")

    # 创建对比表格
    table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
    table.add_column("指标", style="cyan", width=20)
    table.add_column("单进程（基准）", justify="right", width=18)
    table.add_column("多进程（实验）", justify="right", width=18)
    table.add_column("变化", justify="right", width=15)

    # 计算变化
    def calc_change(base, multi):
        if base == 0:
            return "-"
        change = ((multi - base) / base) * 100
        return f"{change:+.1f}%"

    # 添加数据行
    table.add_row(
        "总测试耗时",
        f"{baseline['total_duration']:.2f}s",
        f"{multiprocess['total_duration']:.2f}s",
        calc_change(baseline['total_duration'], multiprocess['total_duration'])
    )

    # 计算加速比
    if multiprocess['total_duration'] > 0:
        speedup = baseline['total_duration'] / multiprocess['total_duration']
    else:
        speedup = 0

    table.add_row(
        "并发加速比",
        "1.00x",
        f"{speedup:.2f}x",
        f"{((speedup - 1) * 100):+.1f}%"
    )

    table.add_row(
        "峰值内存占用",
        f"{baseline['peak_memory']:.1f} MB",
        f"{multiprocess['peak_memory']:.1f} MB",
        calc_change(baseline['peak_memory'], multiprocess['peak_memory'])
    )

    # 计算内存增长比
    if baseline['peak_memory'] > 0:
        memory_ratio = multiprocess['peak_memory'] / baseline['peak_memory']
    else:
        memory_ratio = 0

    table.add_row(
        "内存增长比",
        "1.00x",
        f"{memory_ratio:.2f}x",
        ""
    )

    table.add_row(
        "平均CPU占用",
        f"{baseline['avg_cpu']:.1f}%",
        f"{multiprocess['avg_cpu']:.1f}%",
        calc_change(baseline['avg_cpu'], multiprocess['avg_cpu'])
    )

    console.print(table)
    console.print("\n")

    # 生成评价
    console.rule("[bold yellow]可行性评估", style="yellow")
    console.print("\n")

    checks = []

    # 1. 性能提升评估
    if speedup >= 1.8:
        checks.append(("✅", "性能提升", "优秀", f"加速比 {speedup:.2f}x ≥ 1.8x", "green"))
    elif speedup >= 1.5:
        checks.append(("✅", "性能提升", "良好", f"加速比 {speedup:.2f}x ≥ 1.5x", "green"))
    elif speedup >= 1.2:
        checks.append(("⚠️", "性能提升", "一般", f"加速比 {speedup:.2f}x 在 1.2-1.5x", "yellow"))
    else:
        checks.append(("❌", "性能提升", "不佳", f"加速比 {speedup:.2f}x < 1.2x", "red"))

    # 2. 资源开销评估
    if 1.8 <= memory_ratio <= 2.2:
        checks.append(("✅", "资源开销", "理想", f"内存增长比 {memory_ratio:.2f}x 接近理论值", "green"))
    elif memory_ratio <= 2.5:
        checks.append(("⚠️", "资源开销", "可接受", f"内存增长比 {memory_ratio:.2f}x 略高", "yellow"))
    else:
        checks.append(("❌", "资源开销", "过高", f"内存增长比 {memory_ratio:.2f}x > 2.5x", "red"))

    # 3. 内存限制评估
    if multiprocess['peak_memory'] <= 6000:
        checks.append(("✅", "内存限制", "符合", f"峰值内存 {multiprocess['peak_memory']:.0f}MB ≤ 6GB", "green"))
    elif multiprocess['peak_memory'] <= 8000:
        checks.append(("⚠️", "内存限制", "边缘", f"峰值内存 {multiprocess['peak_memory']:.0f}MB 需要8GB+", "yellow"))
    else:
        checks.append(("❌", "内存限制", "超标", f"峰值内存 {multiprocess['peak_memory']:.0f}MB > 8GB", "red"))

    # 打印检查结果
    for symbol, category, status, reason, color in checks:
        console.print(f"{symbol} [bold]{category}[/bold]: [{color}]{status}[/{color}] - {reason}")

    console.print("\n")

    # 总体结论
    fail_count = sum(1 for check in checks if check[0] == "❌")
    warning_count = sum(1 for check in checks if check[0] == "⚠️")

    if fail_count == 0 and warning_count == 0:
        conclusion = "✅ [bold green]多进程方案完全可行！[/bold green]"
        recommendation = "建议立即应用到生产环境"
    elif fail_count == 0:
        conclusion = "✅ [bold yellow]多进程方案可行，但有优化空间[/bold yellow]"
        recommendation = "建议先小范围试用，持续优化"
    else:
        conclusion = "❌ [bold red]多进程方案需要进一步优化[/bold red]"
        recommendation = "建议先解决性能或资源问题再考虑应用"

    console.print(conclusion)
    console.print(f"\n[cyan]建议：[/cyan]{recommendation}\n")


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="CapsWriter 多进程测试脚本")
    parser.add_argument(
        '--mode',
        choices=['baseline', 'multiprocess', 'compare'],
        default='compare',
        help='测试模式：baseline（基准）、multiprocess（多进程）、compare（完整对比，默认）'
    )

    args = parser.parse_args()

    print_banner()
    print_test_instructions()

    if args.mode in ['baseline', 'compare']:
        baseline_results = await run_baseline_test()

    if args.mode in ['multiprocess', 'compare']:
        multiprocess_results = await run_multiprocess_test()

    if args.mode == 'compare':
        compare_results(baseline_results, multiprocess_results)

    console.print("\n")
    console.rule("[bold cyan]测试完成", style="cyan")
    console.print("\n[green]感谢使用 CapsWriter 测试套件！[/green]\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]测试被用户中断[/yellow]\n")
        sys.exit(0)
