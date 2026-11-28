"""道语言 LSP 服务器测试。

覆盖：初始化握手、帧编解码（中文按字节计算 Content-Length）、正确源码
零诊断、词法/语法错误诊断及行列、关键字/内置函数/标识符补全、悬停、
文档符号、定义跳转、didChange 诊断更新、didClose、错误源码不崩溃，以及
用内存 BytesIO 帧流驱动完整 stdio 链路。
"""

import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.lsp import LanguageServer, features
from dao.lsp.protocol import encode_message, read_message, write_message

GOOD = (
    "定义 甲 = 1\n"
    "函数 加(甲, 乙)\n"
    "  返回 甲 + 乙\n"
    "类型 人\n"
    '  定义 名字 = "张三"\n'
)


def _server():
    """构造一个与真实 stdio 隔离、使用内存流的服务器。"""
    return LanguageServer(input_stream=io.BytesIO(), output_stream=io.BytesIO())


def _request(method, params=None, msg_id=1):
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "method": method,
        "params": params or {},
    }


def _notify(method, params=None):
    return {"jsonrpc": "2.0", "method": method, "params": params or {}}


def _result(outgoing, msg_id):
    """从出站消息列表中取出指定 id 的 result。"""
    for message in outgoing:
        if message.get("id") == msg_id and "result" in message:
            return message["result"]
    raise AssertionError(f"未找到 id={msg_id} 的响应")


def _diagnostics(outgoing):
    """从出站消息列表中取出 publishDiagnostics 的诊断数组。"""
    for message in outgoing:
        if message.get("method") == "textDocument/publishDiagnostics":
            return message["params"]["diagnostics"]
    return []


def _did_open(server, uri, source):
    return server.handle_message(
        _notify(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": uri,
                    "languageId": "dao",
                    "version": 1,
                    "text": source,
                }
            },
        )
    )


# ========================
# 生命周期
# ========================


def test_初始化握手():
    """initialize 返回合理的 serverInfo 与 capabilities。"""
    server = _server()
    out = server.handle_message(
        _request("initialize", {"processId": None, "capabilities": {}}, 1)
    )
    assert out[0]["id"] == 1
    result = out[0]["result"]
    assert result["serverInfo"]["name"] == "道语言服务器"
    caps = result["capabilities"]
    # 增量同步：openClose + change=2（TextDocumentSyncKind.Incremental）
    assert caps["textDocumentSync"] == {"openClose": True, "change": 2}
    assert caps["hoverProvider"] is True
    assert caps["definitionProvider"] is True
    assert caps["referencesProvider"] is True
    assert caps["documentSymbolProvider"] is True
    assert "completionProvider" in caps
    assert set(caps["completionProvider"]["triggerCharacters"]) >= {".", "("}


def test_生命周期_shutdown_exit():
    """initialized/shutdown/exit 按顺序处理，正常退出码为 0。"""
    server = _server()
    assert server.handle_message(_notify("initialized")) == []
    assert _result(server.handle_message(_request("shutdown", {}, 2)), 2) is None
    assert server._shutdown_received is True
    assert server.handle_message(_notify("exit")) == []
    assert server._running is False
    assert server._exit_code == 0


# ========================
# 帧编解码
# ========================


def test_帧编解码_中文按字节计算():
    """含中文的消息 Content-Length 必须等于 UTF-8 字节数，且可往返解码。"""
    msg = {
        "jsonrpc": "2.0",
        "id": 7,
        "method": "测试",
        "params": {"消息": "你好，世界！道语言"},
    }
    frame = encode_message(msg)
    header, sep, body = frame.partition(b"\r\n\r\n")
    assert sep == b"\r\n\r\n"
    length = int(header.decode("ascii").split(":", 1)[1].strip())
    assert length == len(body)
    text = body.decode("utf-8")
    assert len(body) > len(text)  # 中文是多字节，字节数应大于字符数
    assert read_message(io.BytesIO(frame)) == msg
    buffer = io.BytesIO()
    write_message(buffer, msg)
    buffer.seek(0)
    assert read_message(buffer) == msg


def test_帧流_多帧连续读取与EOF():
    """连续多条帧可依次读取，流结束返回 None。"""
    first = {"id": 1, "文字": "中文"}
    second = {"id": 2, "method": "退出"}
    stream = io.BytesIO(encode_message(first) + encode_message(second))
    assert read_message(stream) == first
    assert read_message(stream) == second
    assert read_message(stream) is None
    assert read_message(io.BytesIO(b"")) is None


# ========================
# 诊断
# ========================


def test_正确源码零诊断():
    """正确源码无论是直接分析还是经 didOpen 都产生零诊断。"""
    assert features.compute_diagnostics(GOOD) == []
    server = _server()
    assert _diagnostics(_did_open(server, "file:///a.道", GOOD)) == []
    assert server.documents["file:///a.道"] == GOOD


def test_词法错误诊断行列():
    """非法字符 # 在 1-based(1,8)，转成 0-based(0,7)。

    注：@ 已作为注解前缀成为合法 token，故改用 # 作为非法字符样本。
    """
    diags = features.compute_diagnostics("定义 甲 = #\n")
    assert len(diags) == 1
    diagnostic = diags[0]
    assert diagnostic["range"]["start"] == {"line": 0, "character": 7}
    assert diagnostic["severity"] == 1
    assert diagnostic["source"] == "道语言"
    assert "词法错误" in diagnostic["message"]


def test_语法错误诊断行列():
    """缺变量名的语法错误在 1-based(1,4)，转成 0-based(0,3)。"""
    diags = features.compute_diagnostics("定义 = 1\n")
    assert len(diags) == 1
    assert diags[0]["range"]["start"] == {"line": 0, "character": 3}
    assert "语法错误" in diags[0]["message"]


def test_词法错误零坐标被钳制():
    """未闭合字符串携带 line/column=0，转换后不得出现负坐标。"""
    diags = features.compute_diagnostics('定义 未闭合 = "abc\n')
    assert len(diags) == 1
    start = diags[0]["range"]["start"]
    assert start["line"] >= 0 and start["character"] >= 0


def test_didChange_诊断更新():
    """全量 didChange 后重新发布诊断：出错再改回正确依次变化。"""
    server = _server()
    uri = "file:///a.道"
    _did_open(server, uri, "定义 甲 = 1\n")
    out = server.handle_message(
        _notify(
            "textDocument/didChange",
            {
                "textDocument": {"uri": uri, "version": 2},
                "contentChanges": [{"text": "定义 = 1\n"}],
            },
        )
    )
    diags = _diagnostics(out)
    assert len(diags) == 1 and "语法错误" in diags[0]["message"]
    assert server.documents[uri] == "定义 = 1\n"
    out2 = server.handle_message(
        _notify(
            "textDocument/didChange",
            {
                "textDocument": {"uri": uri, "version": 3},
                "contentChanges": [{"text": "定义 甲 = 2\n"}],
            },
        )
    )
    assert _diagnostics(out2) == []


def test_didClose_清空诊断与移除文档():
    """关闭文档时清空诊断并从内存移除。"""
    server = _server()
    uri = "file:///a.道"
    _did_open(server, uri, GOOD)
    assert uri in server.documents
    out = server.handle_message(
        _notify("textDocument/didClose", {"textDocument": {"uri": uri}})
    )
    assert _diagnostics(out) == []
    assert uri not in server.documents


# ========================
# 补全
# ========================


def test_关键字补全():
    """经 didOpen + completion 请求能拿到关键字候选。"""
    server = _server()
    uri = "file:///a.道"
    _did_open(server, uri, GOOD)
    out = server.handle_message(
        _request(
            "textDocument/completion",
            {"textDocument": {"uri": uri}, "position": {"line": 0, "character": 0}},
            2,
        )
    )
    result = _result(out, 2)
    assert result["isIncomplete"] is False
    items = {item["label"]: item for item in result["items"]}
    assert "函数" in items and items["函数"]["kind"] == 14
    assert "关键字" in items["函数"]["detail"]
    assert "如果" in items and "类型" in items


def test_内置函数与标准库补全():
    """内置函数来自 get_builtins/get_interpreter_builtins，模块来自注册表。"""
    items = {item["label"]: item for item in features.completion_list("")["items"]}
    assert "打印" in items and items["打印"]["kind"] == 3
    assert "映射" in items and items["映射"]["kind"] == 3
    assert "数学" in items and items["数学"]["kind"] == 9
    assert "网络" in items


def test_当前文档标识符补全():
    """当前文档里出现的标识符也进入补全候选。"""
    src = "定义 我的变量 = 42\n设 另一个量 = 我的变量\n"
    labels = {item["label"] for item in features.completion_list(src)["items"]}
    assert "我的变量" in labels
    assert "另一个量" in labels


# ========================
# 悬停 / 符号 / 跳转
# ========================


def test_悬停关键字与内置函数():
    """关键字、内置函数给出中文说明，空白处返回 None。"""
    hover = features.hover_info(GOOD, 1, 1)  # 第 2 行「函数」
    assert hover is not None and "函数" in hover["contents"]["value"]
    assert "关键字" in hover["contents"]["value"]
    builtin = features.hover_info("  打印(1)\n", 0, 3)
    assert builtin is not None and "打印" in builtin["contents"]["value"]
    assert "内置函数" in builtin["contents"]["value"]
    assert features.hover_info(GOOD, 0, 100) is None
    # 经服务器链路
    server = _server()
    uri = "file:///a.道"
    _did_open(server, uri, GOOD)
    out = server.handle_message(
        _request(
            "textDocument/hover",
            {"textDocument": {"uri": uri}, "position": {"line": 1, "character": 1}},
            3,
        )
    )
    assert _result(out, 3) is not None


def test_文档符号含嵌套():
    """顶层函数/类/变量符号，类成员作为 children。"""
    symbols = {s["name"]: s for s in features.document_symbols(GOOD)}
    assert "甲" in symbols and "加" in symbols and "人" in symbols
    assert symbols["加"]["kind"] == 12
    assert symbols["加"]["range"]["start"]["line"] == 1
    assert symbols["人"]["kind"] == 5
    assert any(c["name"] == "名字" for c in symbols["人"].get("children", []))
    # 经服务器链路
    server = _server()
    uri = "file:///a.道"
    _did_open(server, uri, GOOD)
    out = server.handle_message(
        _request("textDocument/documentSymbol", {"textDocument": {"uri": uri}}, 4)
    )
    assert any(s["name"] == "加" for s in _result(out, 4))


def test_定义跳转():
    """光标处的名字可跳转到当前文档内的定义位置。"""
    src = GOOD + "甲\n"
    uri = "file:///x.道"
    locations = features.definition_locations(src, 5, 0, uri)
    assert any(loc["uri"] == uri for loc in locations)
    assert any(loc["range"]["start"]["line"] == 0 for loc in locations)
    server = _server()
    _did_open(server, uri, src)
    out = server.handle_message(
        _request(
            "textDocument/definition",
            {"textDocument": {"uri": uri}, "position": {"line": 5, "character": 0}},
            5,
        )
    )
    assert len(_result(out, 5)) >= 1


# ========================
# 健壮性 / 集成
# ========================


def test_错误源码不崩溃():
    """各类错误源码下所有特性都返回可用结果且不抛异常。"""
    bad_sources = [
        "",
        "定义 = ",
        "函数 (\n",
        '定义 未闭合 = "abc\n',
        "\t混用制表符\n",
        "@@@\n",
        "如果\n",
        "定义 甲 = 1 + \n",
    ]
    for src in bad_sources:
        assert isinstance(features.compute_diagnostics(src), list)
        assert isinstance(features.completion_list(src)["items"], list)
        assert isinstance(features.document_symbols(src), list)
        assert isinstance(
            features.definition_locations(src, 0, 0, "file:///x"), list
        )
        features.hover_info(src, 0, 0)
    server = _server()
    uri = "file:///bad.道"
    _did_open(server, uri, "定义 = @\n")
    methods = (
        "textDocument/completion",
        "textDocument/documentSymbol",
        "textDocument/hover",
        "textDocument/definition",
    )
    for msg_id, method in enumerate(methods, start=10):
        out = server.handle_message(
            _request(
                method,
                {
                    "textDocument": {"uri": uri},
                    "position": {"line": 0, "character": 0},
                },
                msg_id,
            )
        )
        assert any("result" in message for message in out), method
        assert not any("error" in message for message in out), method


def test_未知方法与未知通知():
    """未知请求返回 MethodNotFound，未知通知静默忽略。"""
    server = _server()
    out = server.handle_message(_request("textDocument/不存在", {}, 9))
    assert out[0]["error"]["code"] == -32601
    assert server.handle_message(_notify("随便/通知")) == []


def test_stdio帧流驱动完整链路():
    """用内存帧流驱动 serve()，验证握手→诊断→补全→符号→关闭全过程。"""
    uri = "file:///a.道"
    incoming = [
        _request("initialize", {}, 1),
        _notify(
            "textDocument/didOpen", {"textDocument": {"uri": uri, "text": GOOD}}
        ),
        _request(
            "textDocument/completion",
            {"textDocument": {"uri": uri}, "position": {"line": 0, "character": 0}},
            2,
        ),
        _request("textDocument/documentSymbol", {"textDocument": {"uri": uri}}, 3),
        _request("shutdown", {}, 4),
        _notify("exit"),
    ]
    input_stream = io.BytesIO(b"".join(encode_message(m) for m in incoming))
    output_stream = io.BytesIO()
    server = LanguageServer(input_stream=input_stream, output_stream=output_stream)
    assert server.serve() == 0
    output_stream.seek(0)
    sent = []
    while True:
        message = read_message(output_stream)
        if message is None:
            break
        sent.append(message)
    assert any(
        m.get("id") == 1 and "capabilities" in m.get("result", {}) for m in sent
    )
    assert any(m.get("method") == "textDocument/publishDiagnostics" for m in sent)
    assert any(m.get("id") == 2 and "items" in m.get("result", {}) for m in sent)
    assert any(m.get("id") == 3 for m in sent)
    assert any(m.get("id") == 4 for m in sent)
