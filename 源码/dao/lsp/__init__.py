"""
道语言 LSP（Language Server Protocol）支持包
============================================

纯 Python 标准库实现的语言服务器，通过 JSON-RPC 2.0 over stdio 与编辑器
通信，不依赖 pygls 等第三方库。模块划分：

- :mod:`dao.lsp.protocol`  : 帧编解码（Content-Length 按 UTF-8 字节计算）
- :mod:`dao.lsp.features`  : 诊断、补全、悬停、符号、跳转等语言特性
- :mod:`dao.lsp.server`    : LanguageServer 类与请求分派
- :mod:`dao.lsp.__main__`  : ``python -m dao.lsp`` 启动入口

启动方式::

    cd 源码 && ./.venv/bin/python -m dao.lsp
"""

from .server import LanguageServer

__all__ = ["LanguageServer"]
