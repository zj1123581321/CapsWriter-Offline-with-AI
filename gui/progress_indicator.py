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
import math
from enum import Enum

class ProcessStage(Enum):
    """处理阶段枚举"""
    IDLE = "idle"
    RECORDING = "recording"
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
            # 录音相关
            'recording_start': r'开始录音|正在录音|录音中|按下.*录音',
            'recording_stop': r'录音结束|停止录音|松开.*录音',
            
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
            
        self.window.title("")
        self.window.geometry("120x40")
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
            self.window.winfo_screenwidth() - 140, 50
        ))
        
        # 创建主画布 - 极简黑白风格
        self.main_canvas = tk.Canvas(
            self.window,
            bg='#2a2a2a',
            highlightthickness=0,
            relief='flat'
        )
        self.main_canvas.pack(fill=tk.BOTH, expand=True)
        
        # 设置圆角边框
        self.window.attributes('-alpha', 0.95)
        
        # 移除所有标签，改用canvas绘制
        
        # 动画相关变量
        self._recording_wave_offset = 0
        self._recording_time = 0
        self._icon_pulse = 0
        
        # 为了兼容性，创建虚拟属性
        self.progress_var = type('MockVar', (), {'set': lambda x: None, 'get': lambda: 0})()
        self.status_label = type('MockLabel', (), {'config': lambda **kwargs: None})()
        self.detail_label = type('MockLabel', (), {'config': lambda **kwargs: None})()
        self.time_label = type('MockLabel', (), {'config': lambda **kwargs: None})()
        
        # 移除详细信息标签
        
        # 移除时间信息标签
        
        # 由于使用了 overrideredirect，需要手动添加关闭功能
        # 右键点击窗口隐藏
        def on_right_click(event):
            self.hide()
        
        self.window.bind("<Button-3>", on_right_click)  # 右键隐藏
        
        # 移除关闭提示
        
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
                    self.window.winfo_screenwidth() - 140, 50
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
            if any(keyword in clean_message for keyword in ['转录', 'AI校对', '校对', '录音']):
                print(f"[DEBUG] 进度更新: '{clean_message}'")
            
            # 解析不同类型的日志消息
            if self._match_pattern('recording_start', clean_message):
                self._start_recording()
                
            elif self._match_pattern('recording_stop', clean_message):
                self._stop_recording()
                
            elif self._match_pattern('transcribe_start', clean_message):
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

    def _draw_status_indicator(self, stage=None):
        """绘制状态指示器"""
        self.main_canvas.delete("all")
        canvas_width = self.main_canvas.winfo_width()
        canvas_height = self.main_canvas.winfo_height()
        
        if canvas_width <= 1:  # 画布还未初始化
            self.window.after(50, lambda: self._draw_status_indicator(stage))
            return
        
        center_x = canvas_width // 2
        center_y = canvas_height // 2
        
        if stage == ProcessStage.RECORDING:
            # 录音状态：白色波浪动画
            self._draw_wave_animation(canvas_width, canvas_height)
        elif stage == ProcessStage.TRANSCRIBING:
            # 转录状态：旋转的圆点
            self._draw_transcribe_icon(center_x, center_y)
        elif stage == ProcessStage.AI_PROOFREADING:
            # AI校对状态：脉冲圆圈
            self._draw_ai_icon(center_x, center_y)
        elif stage == ProcessStage.COMPLETED:
            # 完成状态：对勾
            self._draw_check_icon(center_x, center_y)
        else:
            # 默认状态：静止圆点
            self._draw_idle_icon(center_x, center_y)

    def _draw_wave_animation(self, canvas_width, canvas_height):
        """绘制录音状态的白色波浪动画"""
        self._recording_time += 0.15
        
        # 绘制3个白色波浪条
        bar_count = 3
        bar_width = 3
        spacing = 8
        start_x = (canvas_width - (bar_count * bar_width + (bar_count - 1) * spacing)) / 2
        
        for i in range(bar_count):
            # 计算每个条的高度（波浪效果）
            wave_phase = self._recording_time * 3 + i * 0.8
            height_factor = abs(math.sin(wave_phase)) * 0.7 + 0.3  # 0.3 到 1.0
            bar_height = max(4, canvas_height * height_factor * 0.6)
            
            x = start_x + i * (bar_width + spacing)
            y = (canvas_height - bar_height) / 2
            
            # 绘制白色圆角条
            self.main_canvas.create_rectangle(
                x, y, x + bar_width, y + bar_height,
                fill='white', outline='', width=0
            )

    def _draw_transcribe_icon(self, center_x, center_y):
        """绘制转录状态图标（旋转的点）"""
        self._icon_pulse += 0.2
        
        # 绘制3个旋转的点
        for i in range(3):
            angle = self._icon_pulse + i * (2 * math.pi / 3)
            radius = 8
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            
            self.main_canvas.create_oval(
                x - 2, y - 2, x + 2, y + 2,
                fill='white', outline=''
            )

    def _draw_ai_icon(self, center_x, center_y):
        """绘制AI校对状态图标（脉冲圆圈）"""
        self._icon_pulse += 0.3
        
        # 脉冲效果
        pulse_factor = abs(math.sin(self._icon_pulse)) * 0.4 + 0.6
        radius = 8 * pulse_factor
        
        # 绘制脉冲圆圈
        self.main_canvas.create_oval(
            center_x - radius, center_y - radius,
            center_x + radius, center_y + radius,
            outline='white', width=2, fill=''
        )
        
        # 中心点
        self.main_canvas.create_oval(
            center_x - 2, center_y - 2,
            center_x + 2, center_y + 2,
            fill='white', outline=''
        )

    def _draw_check_icon(self, center_x, center_y):
        """绘制完成状态图标（对勾）"""
        # 绘制对勾
        points = [
            center_x - 6, center_y,
            center_x - 2, center_y + 4,
            center_x + 6, center_y - 4
        ]
        self.main_canvas.create_line(
            points, fill='white', width=3, 
            capstyle='round', joinstyle='round'
        )

    def _draw_idle_icon(self, center_x, center_y):
        """绘制空闲状态图标（静止圆点）"""
        self.main_canvas.create_oval(
            center_x - 4, center_y - 4,
            center_x + 4, center_y + 4,
            fill='white', outline=''
        )

    def _draw_rounded_rect(self, canvas, x1, y1, x2, y2, radius, color):
        """绘制圆角矩形"""
        if x2 - x1 < 2 * radius:
            radius = (x2 - x1) / 2
        if y2 - y1 < 2 * radius:
            radius = (y2 - y1) / 2
            
        points = []
        # 左上角
        points.extend([x1 + radius, y1])
        # 右上角
        points.extend([x2 - radius, y1])
        points.extend([x2, y1])
        points.extend([x2, y1 + radius])
        # 右下角
        points.extend([x2, y2 - radius])
        points.extend([x2, y2])
        points.extend([x2 - radius, y2])
        # 左下角
        points.extend([x1 + radius, y2])
        points.extend([x1, y2])
        points.extend([x1, y2 - radius])
        # 回到左上角
        points.extend([x1, y1 + radius])
        points.extend([x1, y1])
        points.extend([x1 + radius, y1])
        
        canvas.create_polygon(points, fill=color, outline="", smooth=True)

    def _draw_gradient_rect(self, canvas, x1, y1, x2, y2, color1, color2, radius):
        """绘制渐变圆角矩形（简化版）"""
        # 简化实现，使用单色
        self._draw_rounded_rect(canvas, x1, y1, x2, y2, radius, color1)

    def _start_recording(self):
        """开始录音阶段"""
        print("[DEBUG] 开始录音阶段")
        self.current_stage = ProcessStage.RECORDING
        self.start_time = datetime.now()
        self._recording_time = 0
        
        # 确保窗口显示
        self.show()
        
        # 开始录音动画
        self._animate_recording_progress()
    
    def _animate_recording_progress(self):
        """录音动画 - 白色波浪效果"""
        if self.current_stage == ProcessStage.RECORDING:
            # 绘制波浪动画
            self._draw_status_indicator(ProcessStage.RECORDING)
            self.window.after(80, self._animate_recording_progress)
    
    def _stop_recording(self):
        """停止录音"""
        if self.current_stage == ProcessStage.RECORDING:
            print("[DEBUG] 停止录音，准备转录")
            self._draw_status_indicator(None)  # 显示默认状态
    
    def start_recording_manually(self):
        """手动开始录音状态 - 供外部调用"""
        self._start_recording()
    
    def stop_recording_manually(self):
        """手动停止录音状态 - 供外部调用"""
        self._stop_recording()

    def _start_transcribing(self):
        """开始转录阶段"""
        print("[DEBUG] 开始转录阶段")
        self.current_stage = ProcessStage.TRANSCRIBING
        self._icon_pulse = 0
        
        if self.start_time is None:
            self.start_time = datetime.now()
        
        # 确保窗口显示
        self.show()
        
        # 开始转录动画
        self._animate_transcribe_progress()

    def _update_transcribe_progress(self, duration):
        """更新转录进度"""
        if self.current_stage == ProcessStage.TRANSCRIBING:
            self.last_progress = duration
            # 继续显示转录动画

    def _transcribe_complete(self):
        """转录完成"""
        if self.current_stage == ProcessStage.TRANSCRIBING:
            self._draw_status_indicator(None)  # 显示默认状态

    def _start_ai_proofreading(self):
        """开始AI校对阶段"""
        print("[DEBUG] 开始AI校对阶段")
        self.current_stage = ProcessStage.AI_PROOFREADING
        self._icon_pulse = 0
        
        # 确保窗口显示
        self.show()
        
        # 开始AI动画
        self._animate_ai_progress()

    def _animate_ai_progress(self):
        """AI校对动画"""
        if self.current_stage == ProcessStage.AI_PROOFREADING:
            self._draw_status_indicator(ProcessStage.AI_PROOFREADING)
            self.window.after(150, self._animate_ai_progress)
            
    def _animate_transcribe_progress(self):
        """转录动画"""
        if self.current_stage == ProcessStage.TRANSCRIBING:
            self._draw_status_indicator(ProcessStage.TRANSCRIBING)
            self.window.after(100, self._animate_transcribe_progress)

    def _ai_complete(self):
        """AI校对完成"""
        if self.current_stage == ProcessStage.AI_PROOFREADING:
            self.current_stage = ProcessStage.COMPLETED
            self._draw_status_indicator(ProcessStage.COMPLETED)
            
            # 0.8秒后自动隐藏
            threading.Timer(0.8, self._auto_hide_after_completion).start()

    def _ai_failed(self):
        """AI校对失败"""
        self.current_stage = ProcessStage.FAILED
        self._draw_status_indicator(None)  # 显示默认状态
        
        # 2秒后自动隐藏
        threading.Timer(2.0, self._auto_hide_after_completion).start()

    def _show_completion_stats(self, transcribe_duration=None, ai_duration=None):
        """显示完成统计信息"""
        # 精简版本不显示统计信息
        pass

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
        self._recording_time = 0
        self._icon_pulse = 0
        
        self._draw_status_indicator(None)
        self.hide()

# 测试代码
if __name__ == "__main__":
    def test_progress():
        root = tk.Tk()
        root.withdraw()  # 隐藏主窗口
        
        indicator = ProgressIndicator()
        
        # 模拟进度更新
        def simulate_progress():
            # 模拟录音阶段
            indicator.update_from_log("开始录音")
            root.after(3000, lambda: indicator.update_from_log("录音结束"))
            
            # 模拟转录阶段
            root.after(4000, lambda: indicator.update_from_log("等待转录结果..."))
            root.after(7000, lambda: indicator.update_from_log("转录完成"))
            
            # 模拟AI校对阶段
            root.after(8000, lambda: indicator.update_from_log("正在进行AI校对..."))
            root.after(11000, lambda: indicator.update_from_log("AI校对：这是校对后的文本"))
        
        root.after(1000, simulate_progress)
        root.mainloop()
    
    test_progress()