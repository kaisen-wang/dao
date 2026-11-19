"""
道语言 LSP 服务器入口
=====================

以 stdio 方式运行语言服务器，供编辑器作为子进程启动::

    cd 源码 && ./.venv/bin/python -m dao.lsp

除 JSON-RPC 帧外不向 stdout 输出任何内容，调试信息也一律不发往 stdout，
以免破坏与客户端之间的帧流。
"""

import sys

from .server import LanguageServer


def main() -> int:
    """创建服务器并运行 stdio 主循环，返回进程退出码。"""
    server = LanguageServer()
    return server.serve()


if __name__ == "__main__":
    sys.exit(main())
