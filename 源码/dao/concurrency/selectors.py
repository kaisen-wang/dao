"""
选择器模块
==========

为道语言提供选择器（Select）实现：
- 基于通道的多路复用选择
- 超时选择支持
"""

import asyncio

from .channels import BufferedChannel, Channel


async def select_receive(cases, timeout=None, timeout_handler=None):
    """异步选择接收操作

    从多个通道中竞速接收数据，返回最先就绪的通道结果。

    Args:
        cases: 列表，每个元素为 (channel, variable_name) 元组
        timeout: 可选超时时间（秒）
        timeout_handler: 超时时的回调函数

    Returns:
        (channel, value) 元组，表示从哪个通道接收到了什么值
        超时时返回 None
    """
    tasks = {}

    for channel, var_name in cases:
        if isinstance(channel, (Channel, BufferedChannel)):
            task = asyncio.create_task(channel.receive_async())
            tasks[task] = (channel, var_name)

    if timeout is not None:
        timeout_task = asyncio.create_task(asyncio.sleep(timeout))
        tasks[timeout_task] = None

    try:
        done, pending = await asyncio.wait(
            tasks.keys(),
            return_when=asyncio.FIRST_COMPLETED,
        )

        # 取消所有未完成的任务
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # 处理完成的任务
        for task in done:
            task_info = tasks[task]
            if task_info is None:
                # 超时任务完成
                if timeout_handler:
                    await timeout_handler()
                return None
            else:
                channel, var_name = task_info
                try:
                    value = task.result()
                    return (channel, var_name, value)
                except StopIteration:
                    # 通道已关闭
                    continue
                except Exception:
                    continue

        return None

    except asyncio.TimeoutError:
        for task in tasks:
            task.cancel()
        if timeout_handler:
            await timeout_handler()
        return None


def select_receive_sync(cases, timeout=None, timeout_handler=None):
    """同步版本的选择接收操作

    Args:
        cases: 列表，每个元素为 (channel, variable_name) 元组
        timeout: 可选超时时间（秒）
        timeout_handler: 超时时的回调函数

    Returns:
        (channel, value) 元组，或超时返回 None
    """
    import time

    start_time = time.time()

    while True:
        for channel, var_name in cases:
            if isinstance(channel, (Channel, BufferedChannel)):
                try:
                    value = channel.queue.get_nowait()
                    return (channel, var_name, value)
                except Exception:
                    continue

        if timeout is not None:
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                if timeout_handler:
                    timeout_handler()
                return None

        time.sleep(0.001)
