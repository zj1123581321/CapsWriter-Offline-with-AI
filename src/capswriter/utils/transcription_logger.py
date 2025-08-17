"""
转录日志记录模块

用于记录原始转录结果和AI校对结果，方便后续问题定位。
日志按照 logs/年份/yyyymm/yyyymmdd.log 的结构存储。
"""

import json
import time
from pathlib import Path
from typing import Optional
from ..config import ClientConfig


class TranscriptionLogger:
    """转录日志记录器"""
    
    def __init__(self, base_dir: Path = None):
        """
        初始化转录日志记录器
        
        Args:
            base_dir: 日志基础目录，默认为项目根目录下的 logs 文件夹
        """
        if base_dir is None:
            # 获取项目根目录
            project_root = Path(__file__).parent.parent.parent.parent
            base_dir = project_root / 'logs'
        
        self.base_dir = base_dir
        self.base_dir.mkdir(exist_ok=True)
    
    def _get_log_file_path(self, timestamp: float) -> Path:
        """
        根据时间戳获取日志文件路径
        
        Args:
            timestamp: Unix时间戳
            
        Returns:
            日志文件的完整路径
        """
        dt = time.localtime(timestamp)
        year = time.strftime('%Y', dt)
        month = time.strftime('%Y%m', dt)
        day = time.strftime('%Y%m%d', dt)
        
        # 创建目录结构：logs/年份/yyyymm/
        log_dir = self.base_dir / year / month
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # 日志文件：yyyymmdd.log
        return log_dir / f'{day}.log'
    
    def log_transcription(
        self,
        timestamp: float,
        original_text: str,
        ai_enhanced_text: Optional[str] = None,
        transcription_delay: float = 0.0,
        ai_duration: float = 0.0,
        task_id: str = ""
    ):
        """
        记录转录结果
        
        Args:
            timestamp: 转录开始时间戳
            original_text: 原始转录结果
            ai_enhanced_text: AI校对后的文本（可选）
            transcription_delay: 转录延迟时间（秒）
            ai_duration: AI校对时长（秒）
            task_id: 任务ID
        """
        # 检查是否启用日志记录
        if not hasattr(ClientConfig, 'enable_transcription_log') or not ClientConfig.enable_transcription_log:
            return
        
        log_file = self._get_log_file_path(timestamp)
        
        # 构建日志条目
        log_entry = {
            'timestamp': timestamp,
            'datetime': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp)),
            'task_id': task_id,
            'original_text': original_text,
            'ai_enhanced_text': ai_enhanced_text,
            'transcription_delay': round(transcription_delay, 2),
            'ai_duration': round(ai_duration, 2),
            'has_ai_enhancement': ai_enhanced_text is not None and ai_enhanced_text != original_text
        }
        
        # 写入日志文件
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        except Exception as e:
            # 日志记录失败不应该影响主要功能
            print(f"警告：转录日志记录失败: {e}")


# 全局日志记录器实例
_logger_instance = None


def get_transcription_logger() -> TranscriptionLogger:
    """获取全局转录日志记录器实例"""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = TranscriptionLogger()
    return _logger_instance


def log_transcription_result(
    timestamp: float,
    original_text: str,
    ai_enhanced_text: Optional[str] = None,
    transcription_delay: float = 0.0,
    ai_duration: float = 0.0,
    task_id: str = ""
):
    """
    记录转录结果的便捷函数
    
    Args:
        timestamp: 转录开始时间戳
        original_text: 原始转录结果
        ai_enhanced_text: AI校对后的文本（可选）
        transcription_delay: 转录延迟时间（秒）
        ai_duration: AI校对时长（秒）
        task_id: 任务ID
    """
    logger = get_transcription_logger()
    logger.log_transcription(
        timestamp=timestamp,
        original_text=original_text,
        ai_enhanced_text=ai_enhanced_text,
        transcription_delay=transcription_delay,
        ai_duration=ai_duration,
        task_id=task_id
    )