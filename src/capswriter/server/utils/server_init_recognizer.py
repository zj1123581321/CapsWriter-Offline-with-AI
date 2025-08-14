import time
from multiprocessing import Queue
import signal
from platform import system

# 检查服务端依赖
try:
    import sherpa_onnx
except ImportError:
    sherpa_onnx = None

from ...config import ServerConfig as Config
try:
    from ...config import ParaformerArgs, ModelPaths
except ImportError:
    ParaformerArgs = None
    ModelPaths = None

from .server_cosmic import console
from .server_recognize import recognize
from ...utils.empty_working_set import empty_current_working_set



def disable_jieba_debug():
    # 关闭 jieba 的 debug
    import jieba
    import logging
    jieba.setLogLevel(logging.INFO)


def init_recognizer(queue_in: Queue, queue_out: Queue, sockets_id):

    # 检查服务端依赖是否安装
    # 使用 global 声明以避免作用域问题
    global sherpa_onnx
    if sherpa_onnx is None:
        console.print('[red bold]错误：缺少服务端依赖！[/red bold]')
        console.print('\n请安装服务端依赖：')
        console.print('[cyan]pip install sherpa-onnx funasr-onnx[/cyan]')
        console.print('\n或者查看文档了解完整的服务端安装步骤')
        queue_out.put(None)  # 通知主进程初始化失败
        return
    
    # Ctrl-C 退出
    signal.signal(signal.SIGINT, lambda signum, frame: exit())

    # 导入模块
    with console.status("载入模块中…", spinner="bouncingBall", spinner_style="yellow"):
        import sherpa_onnx
        try:
            from funasr_onnx import CT_Transformer
        except ImportError:
            console.print('[red]错误：缺少 funasr_onnx 模块[/red]')
            console.print('[cyan]请运行：pip install funasr-onnx[/cyan]')
            queue_out.put(None)
            return
        disable_jieba_debug()
    console.print('[green4]模块加载完成', end='\n\n')

    # 载入语音模型
    console.print('[yellow]语音模型载入中', end='\r'); t1 = time.time()
    
    # 重新导入 sherpa_onnx（避免作用域问题）
    import sherpa_onnx
    
    recognizer = sherpa_onnx.OfflineRecognizer.from_paraformer(
        **{key: value for key, value in ParaformerArgs.__dict__.items() if not key.startswith('_')}
    )
    console.print(f'[green4]语音模型载入完成', end='\n\n')

    # 载入标点模型
    punc_model = None
    if Config.format_punc:
        console.print('[yellow]标点模型载入中', end='\r')
        punc_model = CT_Transformer(ModelPaths.punc_model_dir, quantize=True)
        console.print(f'[green4]标点模型载入完成', end='\n\n')

    console.print(f'模型加载耗时 {time.time() - t1 :.2f}s', end='\n\n')

    # 清空物理内存工作集
    if system() == 'Windows':
        empty_current_working_set()

    queue_out.put(True)  # 通知主进程加载完了

    while True:
        # 从队列中获取任务消息
        # 阻塞最多1秒，便于中断退出
        try:
            task = queue_in.get(timeout=1)       
        except:
            continue

        if task.socket_id not in sockets_id:    # 检查任务所属的连接是否存活
            continue

        result = recognize(recognizer, punc_model, task)   # 执行识别
        queue_out.put(result)      # 返回结果

