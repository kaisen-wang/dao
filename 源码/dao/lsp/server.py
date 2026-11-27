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

from ..version import __version__
from . import features
from .protocol import read_message, write_message

# JSON-RPC 2.0 标准错误码
_METHOD_NOT_FOUND = -32601
_INVALID_PARAMS = -32602
_INTERNAL_ERROR = -32603

SERVER_INFO = {"name": "道语言服务器", "version": __version__}

CAPABILITIES = {
    # TextDocumentSyncOptions：支持打开/关闭通知，变更采用增量同步（2 = Incremental）。
    # 即便声明增量，仍兼容客户端偶发发来的全量帧（contentChanges 无 range）。
    "textDocumentSync": {"openClose": True, "change": 2},
    "completionProvider": {
        "resolveProvider": True,
        # 触发补全的字符；触发时服务器会结合当前作用域过滤候选。
        "triggerCharacters": [".", "("],
    },
    "hoverProvider": True,
    "definitionProvider": True,
    "referencesProvider": True,
    "documentSymbolProvider": True,
    # 基于缩进的源码规范化；支持客户端通过 options.tabSize 指定缩进宽度。
    "documentFormattingProvider": True,
    # 重命名支持 prepareRename，编辑器可先展示占位文本与范围再执行。
    "renameProvider": {"prepareProvider": True},
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
        # 每个已打开文档的最新版本号，用于丢弃乱序 / 重复的 didChange。
        self._versions: dict[str, int] = {}
        # initialize 时从 workspaceFolders / rootUri / rootPath 解析出的工作区根路径。
        self.workspace_roots: list[str] = []
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
            "completionItem/resolve": self._on_completion_resolve,
            "textDocument/hover": self._on_hover,
            "textDocument/definition": self._on_definition,
            "textDocument/references": self._on_references,
            "textDocument/documentSymbol": self._on_document_symbol,
            "textDocument/formatting": self._on_formatting,
            "textDocument/rename": self._on_rename,
            "textDocument/prepareRename": self._on_prepare_rename,
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
        """记录工作区根目录（workspaceFolders 优先，rootUri/rootPath 兜底）。

        URI 形如 ``file:///tmp/%E9%81%93/``，需先按 URI 解码还原中文路径，
        再做规范化。跨文件索引搭建时会用到这些根路径。
        """
        roots: list[str] = []
        for folder in params.get("workspaceFolders") or []:
            if not isinstance(folder, dict):
                continue
            path = features.uri_to_path(folder.get("uri", ""))
            if path and path not in roots:
                roots.append(path)
        # LSP 中 workspaceFolders 与 rootUri 语义重叠：多根优先，单根场景再回退。
        if not roots:
            for key in ("rootUri", "rootPath"):
                path = features.uri_to_path(params.get(key, ""))
                if path and path not in roots:
                    roots.append(path)
        self.workspace_roots = roots
        # 根路径可能变化，旧的工作区索引立即作废。
        features.invalidate_workspace_index()
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
    # 文档同步（增量为主，兼容全量）
    # ========================

    @staticmethod
    def _offset_at(source: str, line: int, character: int) -> int:
        """把 LSP 0-based ``(line, character)`` 转成 Python 字符串下标。

        LSP 的 ``character`` 按 UTF-16 code unit 计数，而 Python 按 Unicode
        code point 索引。对常见中文（BMP）两者一致，因此这里直接按 code point
        处理。增补平面字符（如部分 emoji / 代理对）在 UTF-16 中占两个 code unit、
        在 Python 中只占一个，偏移可能失配；这是当前实现的已知限制（文档亦注明）。
        """
        if line < 0:
            return 0
        lines = source.splitlines(keepends=True)
        if line >= len(lines):
            return len(source)
        text = lines[line]
        # character 指的是行内字符位置，不含行尾符；越界时钳制到行尾。
        content_len = len(text.rstrip("\r\n"))
        char = max(0, min(character, content_len))
        return sum(len(item) for item in lines[:line]) + char

    @classmethod
    def _apply_incremental_edits(cls, source: str, changes: list) -> str:
        """按顺序把 ``contentChanges`` 应用到源码，返回新文本。

        - 带 ``range`` 的变更是增量编辑：范围按 LSP 0-based 行列给出，替换成
          ``text``（``text`` 为空即删除；start==end 即插入）；
        - 无 ``range`` 的变更是兼容帧（Full），整篇替换为 ``text``；
        - 多个变更严格按数组顺序应用，每次基于前一次的结果计算偏移。

        字符位置按 UTF-16 code unit 解释，但仅保证 BMP（含常见中文）正确；
        非 BMP 的代理对见 :meth:`_offset_at` 的说明。
        """
        if not isinstance(changes, list):
            return source
        for change in changes:
            if not isinstance(change, dict):
                continue
            text = change.get("text", "") or ""
            change_range = change.get("range")
            if not isinstance(change_range, dict):
                # 兼容全量帧：整篇替换。
                source = text
                continue
            start_pos = change_range.get("start") or {}
            end_pos = change_range.get("end") or {}
            start = cls._offset_at(source, start_pos.get("line", 0), start_pos.get("character", 0))
            end = cls._offset_at(source, end_pos.get("line", 0), end_pos.get("character", 0))
            if end < start:
                start, end = end, start
            source = source[:start] + text + source[end:]
        return source

    def _on_did_open(self, params) -> tuple:
        uri = self._uri(params)
        document = params.get("textDocument") or {}
        source = document.get("text", "") or ""
        self.documents[uri] = source
        self._versions[uri] = document.get("version", 0)
        features.invalidate_workspace_index()
        return None, [self._diagnostics_notification(uri, source)]

    def _on_did_change(self, params) -> tuple:
        uri = self._uri(params)
        document = params.get("textDocument") or {}
        version = document.get("version")
        current = self._versions.get(uri, 0)
        # 乱序 / 重复帧：旧版本一律忽略（LSP 要求版本单调递增）。
        if version is not None and version <= current:
            return None, []
        changes = params.get("contentChanges") or []
        source = self._apply_incremental_edits(self.documents.get(uri, ""), changes)
        self.documents[uri] = source
        if version is not None:
            self._versions[uri] = version
        else:
            # 客户端未带版本时宽松处理，按一次新编辑推进本地版本。
            self._versions[uri] = current + 1
        features.invalidate_workspace_index()
        return None, [self._diagnostics_notification(uri, source)]

    def _on_did_close(self, params) -> tuple:
        uri = self._uri(params)
        self.documents.pop(uri, None)
        self._versions.pop(uri, None)
        features.invalidate_workspace_index()
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
        uri = self._uri(params)
        source = self.documents.get(uri, "")
        line, character = self._position(params)
        # 按光标处已输入的前缀过滤候选；context（triggerKind / triggerCharacter）
        # 透传给特性层，用于触发场景下进一步收窄作用域候选。
        context = params.get("context") or {}
        prefix = features.word_prefix_at(source, line, character)
        return features.completion_list(
            source, prefix, context=context, position=(line, character)
        ), []

    def _on_completion_resolve(self, params) -> tuple:
        return features.completion_resolve(params), []

    def _on_hover(self, params) -> tuple:
        source = self.documents.get(self._uri(params), "")
        line, character = self._position(params)
        return features.hover_info(source, line, character), []

    def _on_definition(self, params) -> tuple:
        uri = self._uri(params)
        source = self.documents.get(uri, "")
        line, character = self._position(params)
        return (
            features.definition_locations(
                source, line, character, uri, self.workspace_roots, self.documents
            ),
            [],
        )

    def _on_references(self, params) -> tuple:
        uri = self._uri(params)
        source = self.documents.get(uri, "")
        line, character = self._position(params)
        return (
            features.reference_locations(
                source, line, character, uri, self.workspace_roots, self.documents
            ),
            [],
        )

    def _on_document_symbol(self, params) -> tuple:
        source = self.documents.get(self._uri(params), "")
        return features.document_symbols(source), []

    @staticmethod
    def _whole_document_range(source: str) -> dict:
        """覆盖整篇文档的 LSP ``Range``，用于格式化 TextEdit。"""
        lines = source.split("\n")
        return {
            "start": {"line": 0, "character": 0},
            "end": {"line": max(0, len(lines) - 1), "character": len(lines[-1])},
        }

    def _on_formatting(self, params) -> tuple:
        """规范化整篇文档；无变化时不产生编辑。"""
        uri = self._uri(params)
        source = self.documents.get(uri, "")
        formatted = features.format_document(source, params.get("options") or {})
        if formatted == source:
            return [], []
        return (
            [
                {
                    "range": self._whole_document_range(source),
                    "newText": formatted,
                }
            ],
            [],
        )

    def _on_prepare_rename(self, params) -> tuple:
        uri = self._uri(params)
        source = self.documents.get(uri, "")
        line, character = self._position(params)
        return features.prepare_rename(source, line, character), []

    def _on_rename(self, params) -> tuple:
        uri = self._uri(params)
        source = self.documents.get(uri, "")
        line, character = self._position(params)
        return (
            features.rename_edits(
                source,
                line,
                character,
                params.get("newName"),
                uri,
                self.workspace_roots,
                self.documents,
            ),
            [],
        )

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
        except features.重命名错误 as error:
            # 重命名相关的可预期错误直接回传中文消息，便于编辑器提示用户。
            if is_request:
                return [self._error(msg_id, _INVALID_PARAMS, str(error))]
            return []
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
