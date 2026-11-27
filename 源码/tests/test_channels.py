"""通道语义测试：无缓冲 rendezvous、可配置超时、缓冲通道兼容性。"""

import os
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.concurrency.channels import (  # noqa: E402
    DEFAULT_BUFFERED_TIMEOUT,
    DEFAULT_TIMEOUT,
    AsyncBufferedChannel,
    AsyncChannel,
    BufferedChannel,
    Channel,
)
from dao.errors import 运行时错误  # noqa: E402


class TestUnbufferedRendezvous:
    def test_send_blocks_until_receive(self):
        """无缓冲 send 必须阻塞，直到有接收者取走值。"""
        ch = Channel(timeout=2.0)
        done = threading.Event()

        def sender():
            ch.send(42)
            done.set()

        thread = threading.Thread(target=sender)
        thread.start()
        time.sleep(0.1)
        assert not done.is_set(), "send 应在没有接收者时阻塞"

        assert ch.receive(timeout=1.0) == 42
        thread.join(timeout=1.0)
        assert done.is_set(), "接收后 send 应完成"

    def test_receive_blocks_until_send(self):
        """无缓冲 receive 必须阻塞，直到有发送者提供值。"""
        ch = Channel(timeout=2.0)
        received = []

        def receiver():
            received.append(ch.receive(timeout=1.5))

        thread = threading.Thread(target=receiver)
        thread.start()
        time.sleep(0.1)
        assert received == [], "receive 应在没有发送者时阻塞"

        ch.send("你好")
        thread.join(timeout=1.0)
        assert received == ["你好"]

    def test_send_completes_only_when_value_taken(self):
        """接收者真正取走值之后 send 才算完成。"""
        ch = Channel(timeout=2.0)
        events = []

        def sender():
            ch.send(1)
            events.append("发送完成")

        t = threading.Thread(target=sender)
        t.start()
        time.sleep(0.1)
        assert events == []
        assert ch.receive(timeout=1.0) == 1
        t.join(timeout=1.0)
        assert events == ["发送完成"]

    def test_no_buffering_send_times_out_without_receiver(self):
        """没有接收者时，send 在超时后抛错（不会悄悄把值缓存起来）。"""
        ch = Channel(timeout=0.2)
        with pytest.raises(运行时错误, match="发送超时"):
            ch.send(1)
        assert ch.queue.empty(), "超时的值不应残留在通道中"

    def test_receive_times_out_without_sender(self):
        ch = Channel(timeout=0.2)
        with pytest.raises(运行时错误, match="接收超时"):
            ch.receive()

    def test_multiple_senders_rendezvous_in_order(self):
        ch = Channel(timeout=2.0)
        sent = []

        def sender(value):
            ch.send(value)
            sent.append(value)

        threads = [threading.Thread(target=sender, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        time.sleep(0.1)
        assert sent == []

        values = [ch.receive(timeout=1.0) for _ in range(3)]
        for t in threads:
            t.join(timeout=1.0)
        assert sorted(values) == [0, 1, 2]
        assert sorted(sent) == [0, 1, 2]

    def test_default_timeout_is_compatible(self):
        ch = Channel()
        assert ch._timeout == DEFAULT_TIMEOUT == 30.0
        buffered = BufferedChannel(1)
        assert buffered._timeout == DEFAULT_BUFFERED_TIMEOUT == 15.0

    def test_per_call_timeout_overrides_configured(self):
        ch = Channel(timeout=30.0)
        with pytest.raises(运行时错误, match="发送超时"):
            ch.send(1, timeout=0.1)

    def test_close_to_send_raises(self):
        ch = Channel(timeout=2.0)
        ch.close()
        with pytest.raises(运行时错误, match="已关闭"):
            ch.send(1)

    def test_close_to_receive_raises_stop_iteration(self):
        ch = Channel(timeout=2.0)
        ch.close()
        with pytest.raises(StopIteration, match="已关闭"):
            ch.receive()

    def test_close_wakes_blocked_sender(self):
        ch = Channel(timeout=5.0)
        errors = []

        def sender():
            try:
                ch.send(1)
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        t = threading.Thread(target=sender)
        t.start()
        time.sleep(0.1)
        ch.close()
        t.join(timeout=1.0)
        assert len(errors) == 1
        assert "已关闭" in str(errors[0])


class TestQueueViewCompatibility:
    def test_queue_view_get_nowait_after_send(self):
        """select 使用的 queue.get_nowait 应能完成 rendezvous。"""
        ch = Channel(timeout=2.0)
        result = []

        def sender():
            ch.send(7)
            result.append("完成")

        t = threading.Thread(target=sender)
        t.start()
        time.sleep(0.1)
        assert ch.queue.get_nowait() == 7
        t.join(timeout=1.0)
        assert result == ["完成"]

    def test_queue_view_empty(self):
        ch = Channel(timeout=0.2)
        assert ch.queue.empty()
        with pytest.raises(Exception):
            ch.queue.get_nowait()


class TestBufferedChannel:
    def test_buffered_send_does_not_block_until_full(self):
        ch = BufferedChannel(2, timeout=0.5)
        ch.send(1)
        ch.send(2)
        assert ch.receive(timeout=0.5) == 1
        assert ch.receive(timeout=0.5) == 2

    def test_buffered_full_send_times_out(self):
        ch = BufferedChannel(1, timeout=0.2)
        ch.send(1)
        with pytest.raises(运行时错误):
            ch.send(2)

    def test_buffered_empty_receive_times_out(self):
        ch = BufferedChannel(1, timeout=0.2)
        with pytest.raises(运行时错误):
            ch.receive()

    def test_per_call_timeout(self):
        ch = BufferedChannel(1, timeout=30.0)
        ch.send(1)
        with pytest.raises(运行时错误):
            ch.send(2, timeout=0.1)


class TestAsyncChannels:
    def test_async_channel_timeout_default(self):
        ch = AsyncChannel()
        assert ch._timeout == DEFAULT_TIMEOUT

    def test_async_buffered_channel_timeout_default(self):
        ch = AsyncBufferedChannel(1)
        assert ch._timeout == DEFAULT_BUFFERED_TIMEOUT

    def test_async_rendezvous(self):
        import asyncio

        async def scenario():
            ch = AsyncChannel(timeout=1.0)
            sender = asyncio.create_task(ch.send_async(99))
            await asyncio.sleep(0.05)
            assert not sender.done()
            value = await ch.receive_async(timeout=1.0)
            await sender
            return value

        assert asyncio.run(scenario()) == 99
