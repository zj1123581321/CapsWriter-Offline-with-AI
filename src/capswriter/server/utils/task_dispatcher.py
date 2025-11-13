"""
任务分配器

负责将任务根据 task_id 分配到对应的识别进程
"""

from typing import List
from multiprocessing import Queue
from .server_classes import Task


class TaskDispatcher:
    """
    任务分配器

    职责：
    1. 根据 task_id 计算目标进程
    2. 将任务放入对应进程的队列
    3. 保证同一 task_id 的所有片段分配到同一进程
    """

    def __init__(self, queues_in: List[Queue]):
        """
        初始化分配器

        Args:
            queues_in: 输入队列列表，每个进程一个队列
        """
        self.queues_in = queues_in
        self.num_workers = len(queues_in)

    def dispatch(self, task: Task) -> int:
        """
        分配任务到对应进程

        Args:
            task: 待分配的任务

        Returns:
            int: 分配到的进程ID（0-based）
        """
        # 计算目标进程ID
        worker_id = self._get_worker_id(task.task_id)

        # 将任务放入对应队列
        self.queues_in[worker_id].put(task)

        return worker_id

    def _get_worker_id(self, task_id: str) -> int:
        """
        根据 task_id 计算进程ID

        算法：使用 Python 内置的 hash() 函数

        特性：
        - 确定性：同一 task_id 总是映射到同一进程
        - 均匀性：不同 task_id 均匀分布
        - 高效：纯计算，无状态

        Args:
            task_id: 任务ID

        Returns:
            int: 进程ID（0 到 num_workers-1）
        """
        return hash(task_id) % self.num_workers
