# coding: utf-8

"""
测试进度指示器功能
"""

import tkinter as tk
from progress_indicator import ProgressIndicator
import threading
import time

def test_progress_scenarios():
    """测试各种进度场景"""
    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口
    
    indicator = ProgressIndicator()
    
    def simulate_transcription():
        """模拟转录过程"""
        print("开始模拟转录...")
        
        # 1. 等待转录结果
        time.sleep(1)
        indicator.update_from_log("等待转录结果...")
        
        # 2. 转录进度更新 (各种格式)
        time.sleep(2)
        indicator.update_from_log("    转录进度: 5.20秒")
        
        time.sleep(2) 
        indicator.update_from_log("转录进度：12.50s")
        
        time.sleep(2)
        indicator.update_from_log("转录进度: 18.30s")
        
        # 3. 转录完成
        time.sleep(2)
        indicator.update_from_log("转录完成！")
        
        # 4. AI校对开始
        time.sleep(1)
        indicator.update_from_log("    [cyan]正在进行AI校对...")
        
        # 5. AI校对完成
        time.sleep(5)
        indicator.update_from_log("    [cyan]AI校对：这是校对后的文本内容")
        
        # 6. 统计信息
        time.sleep(1)
        indicator.update_from_log("转录耗时：25.8s")
        indicator.update_from_log("AI校对时长：4.2s")
        
        print("模拟完成！")
    
    # 在单独线程中运行模拟
    threading.Thread(target=simulate_transcription, daemon=True).start()
    
    # 添加退出按钮
    test_window = tk.Toplevel()
    test_window.title("进度指示器测试")
    test_window.geometry("300x100")
    
    tk.Label(test_window, text="进度指示器测试运行中...", font=('Arial', 12)).pack(pady=20)
    tk.Button(test_window, text="退出测试", command=root.quit).pack()
    
    root.mainloop()

if __name__ == "__main__":
    test_progress_scenarios()