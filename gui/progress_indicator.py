# coding: utf-8

"""
CapsWriter 进度指示器
实时显示转录和AI校对的进度状态
"""

import tkinter as tk
from tkinter import ttk
import re
from datetime import datetime
import threading
from enum import Enum

class ProcessStage(Enum):
    """处理阶段枚举"""
    IDLE = "idle"
    TRANSCRIBING = "transcribing"  
    AI_PROOFREADING = "ai_proofreading"
    COMPLETED = "completed"
    FAILED = "failed"

class ProgressIndicator:
    """浮动进度指示窗口"""
    
    def __init__(self, parent=None):
        self.parent = parent
        self.window = None
        self.is_visible = False
        self.current_stage = ProcessStage.IDLE
        self.start_time = None
        self.last_progress = 0.0
        
        # 进度解析的正则表达式 - 更宽松的匹配模式
        self.patterns = {
            # 转录相关 - 更宽松的匹配
            'transcribe_start': r'等待转录结果',
            'transcribe_complete': r'转录完成',
            
            # AI校对相关 - 更宽松的匹配
            'ai_start': r'正在进行AI校对|AI校对中|\[cyan\]正在进行AI校对',
            'ai_complete': r'AI校对完成|AI校对：|\[cyan\]AI校对：',
            'ai_failed': r'AI校对失败',
            
            # 统计信息
            'process_duration': r'转录耗时[:：]\s*(\d+\.?\d*)[s秒]',
            'ai_duration': r'AI校对时长[:：]\s*(\d+\.?\d*)[s秒]',
        }
        
        self.create_window()

    def create_window(self):
        """创建浮动进度窗口"""
        # 如果没有父窗口，创建隐藏的根窗口
        if self.parent is None:
            self.root = tk.Tk()
            self.root.withdraw()
            self.window = tk.Toplevel(self.root)
        else:
            self.window = tk.Toplevel(self.parent)
            
        self.window.title("CapsWriter 处理进度")
        self.window.geometry("350x150")
        self.window.resizable(False, False)
        
        # 彻底的无焦点设置
        self.window.overrideredirect(True)  # 移除窗口装饰，防止焦点
        self.window.attributes('-topmost', True)
        self.window.attributes('-alpha', 0.9)
        
        # 设置窗口为工具窗口类型
        try:
            self.window.wm_attributes('-toolwindow', True)
        except:
            pass
        
        # 完全禁用所有焦点相关功能
        self._disable_all_focus_methods()
        
        # 窗口位置 - 屏幕右上角
        self.window.geometry("+{}+{}".format(
            self.window.winfo_screenwidth() - 370, 50
        ))
        
        # 创建主框架 - 为无边框窗口添加视觉边框
        main_frame = tk.Frame(
            self.window, 
            bg='#f0f0f0', 
            relief='solid', 
            borderwidth=1, 
            padx=15, 
            pady=15
        )
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 状态标签 - 使用tk.Label以便设置背景色
        self.status_label = tk.Label(
            main_frame, 
            text="等待处理...", 
            font=('Arial', 12, 'bold'),
            bg='#f0f0f0',
            fg='black'
        )
        self.status_label.pack(pady=(0, 10))
        
        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            main_frame,
            mode='determinate',
            variable=self.progress_var,
            length=300
        )
        self.progress_bar.pack(pady=(0, 10), fill=tk.X)
        
        # 详细信息标签
        self.detail_label = tk.Label(
            main_frame,
            text="",
            font=('Arial', 9),
            fg='gray',
            bg='#f0f0f0'
        )
        self.detail_label.pack()
        
        # 时间信息标签
        self.time_label = tk.Label(
            main_frame,
            text="",
            font=('Arial', 8),
            fg='gray',
            bg='#f0f0f0'
        )
        self.time_label.pack(pady=(5, 0))
        
        # 由于使用了 overrideredirect，需要手动添加关闭功能
        # 右键点击窗口隐藏
        def on_right_click(event):
            self.hide()
        
        self.window.bind("<Button-3>", on_right_click)  # 右键隐藏
        
        # 添加视觉上的关闭提示
        close_btn = tk.Label(
            main_frame,
            text="右键点击隐藏",
            font=('Arial', 8),
            fg='#666666',
            bg='#f0f0f0'
        )
        close_btn.pack(anchor=tk.E, pady=(5, 0))
        
        # 初始隐藏窗口
        self.window.withdraw()
        self.is_visible = False

    def _disable_all_focus_methods(self):
        """彻底禁用所有焦点相关功能"""
        try:
            # 覆盖所有焦点相关方法
            self.window.focus_set = lambda: None
            self.window.focus_force = lambda: None  
            self.window.focus = lambda: None
            self.window.focus_get = lambda: None
            self.window.grab_set = lambda: None
            self.window.grab_set_global = lambda: None
            
            # 禁用键盘输入
            self.window.bind('<Key>', lambda e: "break")
            self.window.bind('<KeyPress>', lambda e: "break")
            self.window.bind('<KeyRelease>', lambda e: "break")
            
            # 绑定焦点事件，立即丢弃
            def ignore_focus(event):
                return "break"
            
            self.window.bind('<FocusIn>', ignore_focus)
            self.window.bind('<FocusOut>', ignore_focus)
            
            print("[DEBUG] 已禁用所有焦点功能")
            
        except Exception as e:
            print(f"[DEBUG] 禁用焦点功能失败: {e}")

    def show(self):
        """显示进度窗口 - 使用overrideredirect确保不抢焦点"""
        if not self.is_visible:
            try:
                # 由于使用了 overrideredirect(True)，窗口不会抢夺焦点
                self.window.deiconify()
                
                # 确保窗口位置正确
                self.window.geometry("+{}+{}".format(
                    self.window.winfo_screenwidth() - 370, 50
                ))
                
                print("[DEBUG] 无焦点进度窗口已显示")
                
            except Exception as e:
                print(f"[DEBUG] 显示进度窗口失败: {e}")
            
            self.is_visible = True

    def hide(self):
        """隐藏进度窗口"""
        if self.is_visible:
            self.window.withdraw()
            self.is_visible = False

    def update_from_log(self, log_message):
        """从日志消息更新进度状态"""
        try:
            # 清除ANSI颜色代码和控制字符
            clean_message = self._clean_ansi(log_message.strip())
            
            # 打印调试信息
            if any(keyword in clean_message for keyword in ['转录', 'AI校对', '校对']):
                print(f"[DEBUG] 进度更新: '{clean_message}'")
            
            # 解析不同类型的日志消息
            if self._match_pattern('transcribe_start', clean_message):
                self._start_transcribing()
                
            elif self._contains_progress_info(clean_message):
                duration = self._extract_progress_duration(clean_message)
                if duration is not None:
                    print(f"[DEBUG] 提取到进度: {duration}秒")
                    # 如果还没有开始转录阶段，先开始
                    if self.current_stage == ProcessStage.IDLE:
                        self._start_transcribing()
                    self._update_transcribe_progress(duration)
                    
            elif self._match_pattern('transcribe_complete', clean_message):
                self._transcribe_complete()
                
            elif self._match_pattern('ai_start', clean_message):
                self._start_ai_proofreading()
                
            elif self._match_pattern('ai_complete', clean_message):
                self._ai_complete()
                
            elif self._match_pattern('ai_failed', clean_message):
                self._ai_failed()
                
            elif self._match_pattern('process_duration', clean_message):
                duration_match = re.search(self.patterns['process_duration'], clean_message)
                if duration_match:
                    duration = float(duration_match.group(1))
                    self._show_completion_stats(transcribe_duration=duration)
                    
        except Exception as e:
            print(f"进度解析错误: {e}: {repr(log_message)}")

    def _clean_ansi(self, text):
        """清除ANSI颜色代码和控制字符"""
        import re
        # 移除ANSI转义序列
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        cleaned = ansi_escape.sub('', text)
        # 移除其他控制字符
        cleaned = re.sub(r'\r|\033\[K', '', cleaned)
        return cleaned.strip()

    def _match_pattern(self, pattern_name, text):
        """检查文本是否匹配指定模式"""
        return bool(re.search(self.patterns[pattern_name], text))
        
    def _contains_progress_info(self, text):
        """检查文本是否包含转录进度信息"""
        # 使用更简单的字符串匹配，而不是复杂的正则表达式
        return '转录进度' in text and any(char.isdigit() for char in text)
    
    def _extract_progress_duration(self, text):
        """从文本中提取进度时长"""
        # 使用更宽松的正则表达式来匹配所有可能的格式
        patterns = [
            # 匹配客户端的具体输出格式
            r'转录进度:\s*(\d+\.?\d*)s',  # "转录进度: 5.20s"
            r'转录进度：\s*(\d+\.?\d*)s',  # "转录进度：12.5s" (中文冒号)
            r'转录进度[:：]\s*(\d+\.?\d*)[s秒]',  # 通用格式
            r'转录进度[:：]\s*(\d+\.?\d*)\s*[s秒]',  # 有空格
            
            # 如果包含"转录进度"，尝试提取任何数字
            r'(\d+\.?\d+)s',  # 数字+s
            r'(\d+\.?\d+)\s*秒',  # 数字+秒
        ]
        
        print(f"[DEBUG] 尝试从文本提取进度: '{text}'")
        
        for i, pattern in enumerate(patterns):
            match = re.search(pattern, text)
            if match:
                try:
                    duration = float(match.group(1))
                    print(f"[DEBUG] 模式{i+1}匹配成功: {duration}")
                    return duration
                except (ValueError, IndexError) as e:
                    print(f"[DEBUG] 模式{i+1}匹配但转换失败: {e}")
                    continue
        
        print(f"[DEBUG] 所有模式都未匹配")
        return None

    def _start_transcribing(self):
        """开始转录阶段"""
        print("[DEBUG] 开始转录阶段，自动显示进度窗口")
        self.current_stage = ProcessStage.TRANSCRIBING
        self.start_time = datetime.now()
        self.progress_var.set(0)
        
        self.status_label.config(text="🎙️ 正在转录...", fg='blue')
        self.detail_label.config(text="正在处理音频数据")
        self.time_label.config(text="")
        
        # 确保窗口显示
        self.show()

    def _update_transcribe_progress(self, duration):
        """更新转录进度"""
        if self.current_stage == ProcessStage.TRANSCRIBING:
            # 这里可以根据音频总长度计算百分比，暂时用时长显示
            self.detail_label.config(text=f"已处理: {duration:.1f} 秒")
            self.last_progress = duration
            
            # 估算进度百分比（假设处理速度）
            estimated_progress = min(duration / 60 * 100, 90)  # 最多90%，留10%给最终处理
            self.progress_var.set(estimated_progress)

    def _transcribe_complete(self):
        """转录完成"""
        if self.current_stage == ProcessStage.TRANSCRIBING:
            self.progress_var.set(50)  # 转录完成是整体进度的50%
            self.detail_label.config(text="转录完成，准备AI校对...")
            
            if self.start_time:
                elapsed = (datetime.now() - self.start_time).total_seconds()
                self.time_label.config(text=f"转录用时: {elapsed:.1f}秒")

    def _start_ai_proofreading(self):
        """开始AI校对阶段"""
        print("[DEBUG] 开始AI校对阶段")
        self.current_stage = ProcessStage.AI_PROOFREADING
        self.progress_var.set(60)
        
        self.status_label.config(text="🤖 AI校对中...", fg='orange')
        self.detail_label.config(text="正在优化和校对文本...")
        
        # 确保窗口显示
        self.show()
        
        # 模拟AI处理进度动画
        self._animate_ai_progress()

    def _animate_ai_progress(self):
        """AI校对进度动画"""
        if self.current_stage == ProcessStage.AI_PROOFREADING:
            current = self.progress_var.get()
            if current < 90:
                self.progress_var.set(current + 2)
                self.window.after(1000, self._animate_ai_progress)

    def _ai_complete(self):
        """AI校对完成"""
        if self.current_stage == ProcessStage.AI_PROOFREADING:
            self.current_stage = ProcessStage.COMPLETED
            self.progress_var.set(100)
            
            self.status_label.config(text="✅ 处理完成", fg='green')
            self.detail_label.config(text="AI校对已完成，文本已优化")
            
            # 3秒后自动隐藏
            threading.Timer(3.0, self._auto_hide_after_completion).start()

    def _ai_failed(self):
        """AI校对失败"""
        self.current_stage = ProcessStage.FAILED
        self.status_label.config(text="⚠️ AI校对失败", fg='red')
        self.detail_label.config(text="转录已完成，但AI校对遇到问题")
        
        # 5秒后自动隐藏
        threading.Timer(5.0, self._auto_hide_after_completion).start()

    def _show_completion_stats(self, transcribe_duration=None, ai_duration=None):
        """显示完成统计信息"""
        if transcribe_duration:
            stats = f"总用时: {transcribe_duration:.1f}秒"
            if ai_duration:
                stats += f" (转录: {transcribe_duration:.1f}s, AI: {ai_duration:.1f}s)"
            self.time_label.config(text=stats)

    def _auto_hide_after_completion(self):
        """完成后自动隐藏"""
        if self.current_stage in [ProcessStage.COMPLETED, ProcessStage.FAILED]:
            self.hide()
            self.current_stage = ProcessStage.IDLE

    def reset(self):
        """重置进度状态"""
        self.current_stage = ProcessStage.IDLE
        self.start_time = None
        self.last_progress = 0.0
        self.progress_var.set(0)
        
        self.status_label.config(text="等待处理...", fg='black')
        self.detail_label.config(text="")
        self.time_label.config(text="")
        
        self.hide()

# 测试代码
if __name__ == "__main__":
    def test_progress():
        root = tk.Tk()
        root.withdraw()  # 隐藏主窗口
        
        indicator = ProgressIndicator()
        
        # 模拟进度更新
        def simulate_progress():
            indicator.update_from_log("等待转录结果...")
            root.after(2000, lambda: indicator.update_from_log("转录进度: 5.2s"))
            root.after(4000, lambda: indicator.update_from_log("转录进度: 15.8s"))
            root.after(6000, lambda: indicator.update_from_log("转录完成"))
            root.after(7000, lambda: indicator.update_from_log("正在进行AI校对..."))
            root.after(10000, lambda: indicator.update_from_log("AI校对：这是校对后的文本"))
            root.after(11000, lambda: indicator.update_from_log("转录耗时：18.5s"))
        
        root.after(1000, simulate_progress)
        root.mainloop()
    
    test_progress()