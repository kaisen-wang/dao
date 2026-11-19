"""
LSP 传输层：JSON-RPC 2.0 帧读写
================================

语言服务器通过标准输入输出（stdio）与编辑器通信。每条消息都带有形如
``Content-Length: <字节数>`` 的帧头，帧头与正文以空行分隔，正文是 UTF-8
编码的 JSON 文本。

本模块仅依赖 Python 标准库，提供三个函数：

- :func:`encode_message` : 把一条消息编码为完整帧（帧头 + 正文）的字节串；
- :func:`write_message`  : 把一条消息写入二进制流并刷新缓冲区；
- :func:`read_message`   : 从二进制流读取一帧并解析为字典。

关键约束：``Content-Length`` 必须是正文 **UTF-8 编码后的字节数**，而非
字符数。中文字符通常占 3 个字节，若误按字符数填充，客户端会截断正文或
把下一条帧误认成正文，导致协议错乱。
"""

import json


def encode_message(message: dict) -> bytes:
    """把一条 JSON-RPC 消息编码为完整的 LSP 帧（帧头 + 正文）。

    使用 ``ensure_ascii=False`` 让中文以 UTF-8 原样写入，再按编码后的字节
    长度填写 ``Content-Length``，保证多字节字符被正确计数。
    """
    body = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
    return header + body


def write_message(stream, message: dict) -> None:
    """向二进制流写出一条消息，并立即刷新缓冲区。

    stdio 通信必须及时 ``flush``，否则客户端会一直等待而收不到响应。
    """
    stream.write(encode_message(message))
    flush = getattr(stream, "flush", None)
    if flush is not None:
        flush()


def read_message(stream) -> dict | None:
    """从二进制流读取一条 JSON-RPC 消息。

    逐行解析帧头，找到 ``Content-Length`` 后按 **字节数** 读取正文，再以
    UTF-8 解码并反序列化为字典。到达流末尾且没有新消息时返回 ``None``，
    供主循环优雅退出。帧头缺失或非法时抛出 :class:`ValueError`，由调用方
    决定跳过坏帧，避免污染 stdio 通道。
    """
    content_length = None
    while True:
        line = stream.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        text = line.decode("ascii", errors="replace").strip()
        name, sep, value = text.partition(":")
        if sep and name.strip().lower() == "content-length":
            try:
                content_length = int(value.strip())
            except ValueError:
                content_length = None
    if content_length is None or content_length < 0:
        raise ValueError("无效的 Content-Length 帧头")
    body = stream.read(content_length)
    while len(body) < content_length:
        chunk = stream.read(content_length - len(body))
        if not chunk:
            break
        body += chunk
    return json.loads(body.decode("utf-8"))
