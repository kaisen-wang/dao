"""
道语言 LSP 服务器
=================

实现 Language Server Protocol 的服务器主体：消息分派、生命周期管理、
内存文档同步，并把 :mod:`dao.lsp.features` 的语言特性结果封装成 JSON-RPC
响应或通知。

设计：

- :meth:`LanguageServer.handle_message` 是 **无副作用** 的分派核心，返回
  「需要发回客户端的消息列表」。测试无需启动真实进程即可直接断言分派结果；
- :meth:`LanguageServer.serve` 只负责从输入流读帧、调用分派、把出站消息
  写回输出流；
- 任何单条消息的处理异常都会被兜底成 JSON-RPC 错误响应，绝不让服务器崩溃；
- 绝不向 stdout 打印调试信息，以免破坏 stdio 帧流。
"""

import sys

from . import features
from .protocol import read_message, write_message

# JSON-RPC 2.0 标准错误码
_METHOD_NOT_FOUND = -32601
_INTERNAL_ERROR = -32603

SERVER_INFO = {"name": "道语言服务器", "version": "0.1.0"}

CAPABILITIES = {
    "textDocumentSync": 1,  # 1 = 全量同步（TextDocumentSyncKind.Full）
    "completionProvider": {"resolveProvider": False},
    "hoverProvider": True,
    "definitionProvider": True,
    "documentSymbolProvider": True,
}


class LanguageServer:
    """道语言 LSP 服务器。

    参数：
        input_stream  : 二进制输入流，默认 ``sys.stdin.buffer``；
        output_stream : 二进制输出流，默认 ``sys.stdout.buffer``。

    测试时可注入 :class:`io.BytesIO` 以内存帧流驱动，避免触碰真实 stdio。
    """

    def __init__(self, input_stream=None, output_stream=None):
        self.input_stream = (
            input_stream if input_stream is not None else sys.stdin.buffer
        )
        self.output_stream = (
            output_stream if output_stream is not None else sys.stdout.buffer
        )
        self.documents: dict[str, str] = {}
        self._shutdown_received = False
        self._running = False
        self._exit_code = 0
        self._handlers = {
            "initialize": self._on_initialize,
            "initialized": self._on_initialized,
            "shutdown": self._on_shutdown,
            "exit": self._on_exit,
            "textDocument/didOpen": self._on_did_open,
            "textDocument/didChange": self._on_did_change,
            "textDocument/didClose": self._on_did_close,
            "textDocument/completion": self._on_completion,
            "textDocument/hover": self._on_hover,
            "textDocument/definition": self._on_definition,
            "textDocument/documentSymbol": self._on_document_symbol,
        }

    # ========================
    # 出站消息构造
    # ========================

    @staticmethod
    def _response(msg_id, result) -> dict:
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    @staticmethod
    def _error(msg_id, code: int, message: str) -> dict:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": code, "message": message},
        }

    def _diagnostics_notification(self, uri: str, source: str) -> dict:
        return {
            "jsonrpc": "2.0",
            "method": "textDocument/publishDiagnostics",
            "params": {
                "uri": uri,
                "diagnostics": features.compute_diagnostics(source),
            },
        }

    @staticmethod
    def _uri(params: dict) -> str:
        return (params.get("textDocument") or {}).get("uri", "")

    @staticmethod
    def _position(params: dict) -> tuple[int, int]:
        position = params.get("position") or {}
        return position.get("line", 0), position.get("character", 0)

    # ========================
    # 生命周期
    # ========================

    def _on_initialize(self, params) -> tuple:
        return {"capabilities": CAPABILITIES, "serverInfo": SERVER_INFO}, []

    def _on_initialized(self, params) -> tuple:
        return None, []

    def _on_shutdown(self, params) -> tuple:
        self._shutdown_received = True
        return None, []

    def _on_exit(self, params) -> tuple:
        self._running = False
        # LSP 规定：未经 shutdown 直接 exit 时退出码应为 1。
        self._exit_code = 0 if self._shutdown_received else 1
        return None, []

    # ========================
    # 文档同步（全量）
    # ========================

    def _on_did_open(self, params) -> tuple:
        uri = self._uri(params)
        source = (params.get("textDocument") or {}).get("text", "") or ""
        self.documents[uri] = source
        return None, [self._diagnostics_notification(uri, source)]

    def _on_did_change(self, params) -> tuple:
        uri = self._uri(params)
        changes = params.get("contentChanges") or []
        if changes:
            # 全量同步：每条变更都是完整文本，取最新一条。
            source = changes[-1].get("text", "") or ""
            self.documents[uri] = source
        else:
            source = self.documents.get(uri, "")
        return None, [self._diagnostics_notification(uri, source)]

    def _on_did_close(self, params) -> tuple:
        uri = self._uri(params)
        self.documents.pop(uri, None)
        # 关闭文档时清空该 URI 的诊断。
        empty = {
            "jsonrpc": "2.0",
            "method": "textDocument/publishDiagnostics",
            "params": {"uri": uri, "diagnostics": []},
        }
        return None, [empty]

    # ========================
    # 语言特性
    # ========================

    def _on_completion(self, params) -> tuple:
        source = self.documents.get(self._uri(params), "")
        return features.completion_list(source), []

    def _on_hover(self, params) -> tuple:
        source = self.documents.get(self._uri(params), "")
        line, character = self._position(params)
        return features.hover_info(source, line, character), []

    def _on_definition(self, params) -> tuple:
        uri = self._uri(params)
        source = self.documents.get(uri, "")
        line, character = self._position(params)
        return features.definition_locations(source, line, character, uri), []

    def _on_document_symbol(self, params) -> tuple:
        source = self.documents.get(self._uri(params), "")
        return features.document_symbols(source), []

    # ========================
    # 分派与主循环
    # ========================

    def handle_message(self, msg: dict) -> list[dict]:
        """处理一条客户端消息，返回需要发回的消息列表。

        对请求（带 ``id``）会在列表末尾附加响应；对通知（无 ``id``）只返回
        可能产生的服务端通知（如 ``publishDiagnostics``）。未知方法返回
        ``MethodNotFound`` 错误响应；单条消息的处理异常被兜底为内部错误。
        """
        if not isinstance(msg, dict):
            return []
        method = msg.get("method")
        if not method:
            # 客户端发来的响应消息，服务端无需处理。
            return []
        is_request = "id" in msg
        msg_id = msg.get("id")
        params = msg.get("params") or {}
        handler = self._handlers.get(method)
        if handler is None:
            if is_request:
                return [
                    self._error(msg_id, _METHOD_NOT_FOUND, f"未实现的方法：{method}")
                ]
            return []
        try:
            result, notifications = handler(params)
        # 有意宽泛捕获：错误源码时降级返回已有信息，绝不让 LSP 服务器崩溃
        except Exception as error:  # noqa: BLE001
            if is_request:
                return [
                    self._error(
                        msg_id,
                        _INTERNAL_ERROR,
                        f"处理「{method}」时发生内部错误：{type(error).__name__}",
                    )
                ]
            return []
        outgoing = list(notifications)
        if is_request:
            outgoing.append(self._response(msg_id, result))
        return outgoing

    def serve(self) -> int:
        """运行 stdio 主循环直到收到 ``exit`` 或输入流结束，返回进程退出码。

        损坏的帧（非法 Content-Length、非 UTF-8、非法 JSON）会被跳过，不会
        中断服务器，也不会向 stdout 输出任何内容。
        """
        self._running = True
        while self._running:
            try:
                msg = read_message(self.input_stream)
            except ValueError:
                continue
            if msg is None:
                break
            for outgoing in self.handle_message(msg):
                write_message(self.output_stream, outgoing)
        return self._exit_code
