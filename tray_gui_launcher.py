# coding: utf-8

"""
CapsWriter 客户端托盘启动器（带GUI日志窗口）
功能：
1. 一键启动客户端
2. 最小化到系统托盘
3. 点击托盘图标或菜单显示/隐藏主窗口
4. 实时显示客户端日志
5. 不在 Alt+Tab 中显示（可选）
"""

import sys
import os
import subprocess
import threading
import queue
from pathlib import Path
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import pystray
from PIL import Image, ImageDraw
import signal
import time
from datetime import datetime
from progress_indicator import ProgressIndicator

class CapsWriterGUI:
    def __init__(self):
        self.client_process = None
        self.is_running = False
        self.log_queue = queue.Queue()
        
        # 窗口状态 - 必须在setup_tray之前初始化
        self.window_visible = True
        
        # 设置项目根目录
        self.project_root = Path(__file__).parent
        self.client_script = self.project_root / "scripts" / "start_client.py"
        self.python_exe = self.project_root / "venv" / "Scripts" / "python.exe"
        
        # 创建主窗口
        self.root = tk.Tk()
        self.setup_window()
        self.setup_widgets()
        
        # 创建进度指示器
        self.progress_indicator = ProgressIndicator(parent=self.root)
        
        # 创建托盘图标
        self.tray_icon = None
        self.setup_tray()

    def setup_window(self):
        """设置主窗口"""
        self.root.title("CapsWriter 客户端控制台")
        self.root.geometry("800x600")
        self.root.minsize(600, 400)
        
        # 设置窗口图标（如果有的话）
        try:
            icon_path = self.project_root / "assets" / "icon.ico"
            if icon_path.exists():
                self.root.iconbitmap(str(icon_path))
        except:
            pass
        
        # 绑定窗口关闭事件 - 现在关闭窗口会完全退出应用程序
        self.root.protocol("WM_DELETE_WINDOW", self.exit_application)
        
        # 绑定窗口状态变化事件
        self.root.bind('<Unmap>', self.on_window_minimize)

    def setup_widgets(self):
        """设置界面组件"""
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        # 状态标签
        self.status_label = ttk.Label(main_frame, text="客户端状态: 已停止", font=('Arial', 12, 'bold'))
        self.status_label.grid(row=0, column=0, columnspan=3, pady=(0, 10), sticky=tk.W)
        
        # 控制按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=1, column=0, columnspan=3, pady=(0, 10), sticky=(tk.W, tk.E))
        
        self.start_btn = ttk.Button(button_frame, text="启动客户端", command=self.start_client)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.stop_btn = ttk.Button(button_frame, text="停止客户端", command=self.stop_client, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.restart_btn = ttk.Button(button_frame, text="重启客户端", command=self.restart_client, state=tk.DISABLED)
        self.restart_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.clear_btn = ttk.Button(button_frame, text="清空日志", command=self.clear_log)
        self.clear_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.hide_btn = ttk.Button(button_frame, text="隐藏到托盘", command=self.hide_window)
        self.hide_btn.pack(side=tk.RIGHT, padx=(0, 5))
        
        self.progress_btn = ttk.Button(button_frame, text="进度提示", command=self.toggle_progress_indicator)
        self.progress_btn.pack(side=tk.RIGHT, padx=(0, 5))
        
        self.exit_btn = ttk.Button(button_frame, text="退出程序", command=self.exit_application)
        self.exit_btn.pack(side=tk.RIGHT)
        
        # 日志显示区域
        log_frame = ttk.LabelFrame(main_frame, text="客户端日志", padding="5")
        log_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        # 日志文本框
        self.log_text = scrolledtext.ScrolledText(
            log_frame, 
            wrap=tk.WORD, 
            state=tk.DISABLED,
            font=('Consolas', 9)
        )
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置文本颜色
        self.log_text.tag_configure("info", foreground="blue")
        self.log_text.tag_configure("warning", foreground="orange")
        self.log_text.tag_configure("error", foreground="red")
        self.log_text.tag_configure("success", foreground="green")
        
        # 启动日志更新定时器
        self.update_log_display()

    def create_tray_icon(self):
        """创建托盘图标"""
        width = 64
        height = 64
        image = Image.new('RGBA', (width, height), color=(0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # 绘制一个麦克风图标
        if self.is_running:
            # 运行状态 - 绿色
            color = (0, 200, 0)
        else:
            # 停止状态 - 灰色
            color = (128, 128, 128)
        
        draw.ellipse([16, 12, 48, 36], fill=color)  # 麦克风头
        draw.rectangle([28, 36, 36, 52], fill=color)  # 麦克风柄
        draw.rectangle([20, 52, 44, 56], fill=color)  # 底座
        
        return image

    def setup_tray(self):
        """设置系统托盘"""
        def create_menu():
            if self.window_visible:
                show_hide_text = "隐藏窗口"
                show_hide_action = self.hide_window
            else:
                show_hide_text = "显示窗口"
                show_hide_action = self.show_window
            
            status_text = "运行中" if self.is_running else "已停止"
            
            return pystray.Menu(
                pystray.MenuItem(f"CapsWriter - {status_text}", None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(show_hide_text, show_hide_action),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("启动客户端", self.start_client, enabled=not self.is_running),
                pystray.MenuItem("停止客户端", self.stop_client, enabled=self.is_running),
                pystray.MenuItem("重启客户端", self.restart_client, enabled=self.is_running),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("打开配置文件夹", self.open_config_folder),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("进度提示窗口", self.toggle_progress_indicator),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("退出", self.exit_application)
            )
        
        self.tray_icon = pystray.Icon(
            "CapsWriter",
            self.create_tray_icon(),
            "CapsWriter 客户端",
            menu=create_menu()
        )
        
        # 单击托盘图标显示/隐藏窗口
        self.tray_icon.action = self.toggle_window
        
        # 在单独的线程中运行托盘图标
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def update_tray(self):
        """更新托盘图标和菜单"""
        if self.tray_icon:
            self.tray_icon.icon = self.create_tray_icon()
            
            # 更新菜单
            def create_menu():
                if self.window_visible:
                    show_hide_text = "隐藏窗口"
                    show_hide_action = self.hide_window
                else:
                    show_hide_text = "显示窗口"
                    show_hide_action = self.show_window
                
                status_text = "运行中" if self.is_running else "已停止"
                
                return pystray.Menu(
                    pystray.MenuItem(f"CapsWriter - {status_text}", None, enabled=False),
                    pystray.Menu.SEPARATOR,
                    pystray.MenuItem(show_hide_text, show_hide_action),
                    pystray.Menu.SEPARATOR,
                    pystray.MenuItem("启动客户端", self.start_client, enabled=not self.is_running),
                    pystray.MenuItem("停止客户端", self.stop_client, enabled=self.is_running),
                    pystray.MenuItem("重启客户端", self.restart_client, enabled=self.is_running),
                    pystray.Menu.SEPARATOR,
                    pystray.MenuItem("打开配置文件夹", self.open_config_folder),
                    pystray.Menu.SEPARATOR,
                    pystray.MenuItem("进度提示窗口", self.toggle_progress_indicator),
                    pystray.Menu.SEPARATOR,
                    pystray.MenuItem("退出", self.exit_application)
                )
            
            self.tray_icon.menu = create_menu()

    def log_message(self, message, level="info", update_progress=True):
        """添加日志消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}\n"
        self.log_queue.put((formatted_message, level))
        
        # 同时更新进度指示器（可选，避免重复更新）
        if update_progress and self.progress_indicator:
            self.progress_indicator.update_from_log(message)

    def update_log_display(self):
        """更新日志显示"""
        try:
            while not self.log_queue.empty():
                message, level = self.log_queue.get_nowait()
                
                self.log_text.config(state=tk.NORMAL)
                self.log_text.insert(tk.END, message, level)
                self.log_text.see(tk.END)
                self.log_text.config(state=tk.DISABLED)
        except queue.Empty:
            pass
        
        # 每100ms更新一次
        self.root.after(100, self.update_log_display)

    def clear_log(self):
        """清空日志"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.log_message("日志已清空", "info")

    def start_client(self):
        """启动客户端"""
        if self.is_running:
            return
        
        try:
            # 检查文件是否存在
            if not self.python_exe.exists():
                self.log_message(f"错误：未找到Python可执行文件: {self.python_exe}", "error")
                return
                
            if not self.client_script.exists():
                self.log_message(f"错误：未找到客户端脚本: {self.client_script}", "error")
                return
            
            self.log_message("正在启动客户端...", "info")
            
            # 重置进度指示器
            if self.progress_indicator:
                self.progress_indicator.reset()
            
            # 启动客户端进程
            self.client_process = subprocess.Popen(
                [str(self.python_exe), str(self.client_script)],
                cwd=str(self.project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            self.is_running = True
            self.update_ui_state()
            self.log_message("客户端启动成功", "success")
            
            # 监控进程输出
            threading.Thread(target=self.monitor_output, daemon=True).start()
            # 监控进程状态
            threading.Thread(target=self.monitor_process, daemon=True).start()
            
        except Exception as e:
            self.log_message(f"启动失败: {str(e)}", "error")

    def stop_client(self):
        """停止客户端"""
        if not self.is_running or not self.client_process:
            return
        
        try:
            self.log_message("正在停止客户端...", "info")
            
            # 优雅地终止进程
            self.client_process.terminate()
            
            # 等待进程结束，最多等待5秒
            try:
                self.client_process.wait(timeout=5)
                self.log_message("客户端已停止", "success")
            except subprocess.TimeoutExpired:
                # 如果进程没有响应，强制终止
                self.client_process.kill()
                self.client_process.wait()
                self.log_message("强制终止客户端", "warning")
            
            self.client_process = None
            self.is_running = False
            self.update_ui_state()
            
            # 隐藏进度指示器
            if self.progress_indicator:
                self.progress_indicator.hide()
            
        except Exception as e:
            self.log_message(f"停止失败: {str(e)}", "error")

    def restart_client(self):
        """重启客户端"""
        self.log_message("重启客户端中...", "info")
        self.stop_client()
        threading.Timer(2.0, self.start_client).start()

    def monitor_output(self):
        """监控客户端输出"""
        if not self.client_process:
            return
        
        try:
            # 保存当前进程引用，避免在监控过程中被置为None
            process = self.client_process
            while process and process.poll() is None:
                # 双重检查进程是否还存在
                if not self.client_process or self.client_process != process:
                    break
                    
                line = process.stdout.readline()
                if line:
                    # 根据内容判断日志级别
                    line = line.strip()
                    
                    # 先更新进度指示器（直接用原始输出）
                    if self.progress_indicator:
                        # 添加调试输出
                        if any(keyword in line for keyword in ['转录', 'AI校对', '校对']):
                            print(f"[GUI DEBUG] 向进度指示器发送: {line}")
                        self.progress_indicator.update_from_log(line)
                    
                    # 然后添加到GUI日志（不重复更新进度）
                    if "错误" in line or "ERROR" in line or "Exception" in line:
                        self.log_message(line, "error", update_progress=False)
                    elif "警告" in line or "WARNING" in line:
                        self.log_message(line, "warning", update_progress=False)
                    elif "成功" in line or "SUCCESS" in line or "完成" in line:
                        self.log_message(line, "success", update_progress=False)
                    else:
                        self.log_message(line, "info", update_progress=False)
        except Exception as e:
            self.log_message(f"监控输出时出错: {str(e)}", "error")

    def monitor_process(self):
        """监控客户端进程状态"""
        if self.client_process:
            # 保存当前进程引用，避免在等待过程中被置为None
            process = self.client_process
            try:
                process.wait()  # 等待进程结束
                # 检查是否是意外退出（进程引用仍然匹配且标记为运行中）
                if self.is_running and self.client_process == process:
                    self.log_message("客户端进程异常退出", "error")
                    self.is_running = False
                    self.client_process = None
                    self.update_ui_state()
            except Exception as e:
                self.log_message(f"监控进程时出错: {str(e)}", "error")

    def update_ui_state(self):
        """更新UI状态"""
        if self.is_running:
            self.status_label.config(text="客户端状态: 运行中", foreground="green")
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.restart_btn.config(state=tk.NORMAL)
        else:
            self.status_label.config(text="客户端状态: 已停止", foreground="red")
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
            self.restart_btn.config(state=tk.DISABLED)
        
        self.update_tray()

    def show_window(self):
        """显示窗口"""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.window_visible = True
        self.update_tray()

    def hide_window(self):
        """隐藏窗口到托盘"""
        self.root.withdraw()
        self.window_visible = False
        self.update_tray()
        self.log_message("窗口已隐藏到系统托盘，要完全退出请右键托盘图标选择'退出'", "info")

    def toggle_window(self):
        """切换窗口显示/隐藏状态"""
        if self.window_visible:
            self.hide_window()
        else:
            self.show_window()

    def on_window_minimize(self, event):
        """窗口最小化时的处理"""
        if event.widget == self.root:
            # 可选：最小化时自动隐藏到托盘
            # self.hide_window()
            pass

    def toggle_progress_indicator(self):
        """切换进度指示器显示状态"""
        if self.progress_indicator:
            if self.progress_indicator.is_visible:
                self.progress_indicator.hide()
                self.log_message("进度提示窗口已隐藏", "info")
            else:
                # 显示窗口
                self.progress_indicator.show()
                self.log_message("进度提示窗口已显示", "info")

    def test_progress_indicator(self):
        """测试进度指示器功能"""
        def run_test():
            time.sleep(1)
            self.progress_indicator.update_from_log("等待转录结果...")
            time.sleep(2)
            self.progress_indicator.update_from_log("转录进度: 5.20秒")
            time.sleep(2)
            self.progress_indicator.update_from_log("转录进度：12.5s")
            time.sleep(2)
            self.progress_indicator.update_from_log("转录完成！")
            time.sleep(1)
            self.progress_indicator.update_from_log("正在进行AI校对...")
            time.sleep(3)
            self.progress_indicator.update_from_log("AI校对：优化后的文本")
        
        threading.Thread(target=run_test, daemon=True).start()

    def open_config_folder(self):
        """打开配置文件夹"""
        try:
            os.startfile(str(self.project_root))
        except Exception as e:
            self.log_message(f"无法打开配置文件夹: {str(e)}", "error")

    def exit_application(self):
        """退出应用程序"""
        self.log_message("正在退出应用程序...", "info")
        
        if self.is_running:
            self.stop_client()
            time.sleep(1)  # 等待客户端停止
        
        if self.tray_icon:
            self.tray_icon.stop()
            
        # 关闭进度指示器
        if self.progress_indicator:
            self.progress_indicator.hide()
        
        self.root.quit()
        sys.exit(0)

    def run(self):
        """运行应用程序"""
        # 设置信号处理器
        signal.signal(signal.SIGINT, lambda s, f: self.exit_application())
        signal.signal(signal.SIGTERM, lambda s, f: self.exit_application())
        
        self.log_message("CapsWriter 客户端控制台已启动", "success")
        self.log_message("提示：可以点击 '隐藏到托盘' 或关闭窗口来隐藏到系统托盘", "info")
        
        # 启动时自动启动客户端
        self.log_message("自动启动客户端...", "info")
        threading.Timer(1.0, self.start_client).start()  # 延迟1秒启动，确保GUI完全加载
        
        # 运行主循环
        self.root.mainloop()

def main():
    """主函数"""
    try:
        app = CapsWriterGUI()
        app.run()
    except KeyboardInterrupt:
        print("程序被用户中断")
    except Exception as e:
        messagebox.showerror("错误", f"程序运行出错: {str(e)}")

if __name__ == "__main__":
    main()