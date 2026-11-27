"""LSP 格式化与重命名能力测试。

覆盖：能力声明、``textDocument/formatting`` 的 TextEdit 与 tabSize、
``textDocument/rename`` 的单文件 / 跨文件 WorkspaceEdit 与范围限制、
``textDocument/prepareRename`` 的正常返回与中文错误边界。
"""

import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.lsp import LanguageServer


def _server():
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
    for message in outgoing:
        if message.get("id") == msg_id and "result" in message:
            return message["result"]
    raise AssertionError(f"未找到 id={msg_id} 的响应")


def _error(outgoing, msg_id):
    for message in outgoing:
        if message.get("id") == msg_id and "error" in message:
            return message["error"]
    raise AssertionError(f"未找到 id={msg_id} 的错误响应")


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


def _initialize(server, root):
    return _result(
        server.handle_message(
            _request(
                "initialize",
                {"rootUri": root.as_uri(), "capabilities": {}},
                99,
            )
        ),
        99,
    )


# ========================
# 能力声明与格式化
# ========================


def test_能力声明包含格式化与重命名():
    server = _server()
    caps = _result(server.handle_message(_request("initialize", {}, 1)), 1)[
        "capabilities"
    ]
    assert caps["documentFormattingProvider"] is True
    assert caps["renameProvider"] == {"prepareProvider": True}


def test_formatting_返回整篇TextEdit():
    server = _server()
    uri = "file:///fmt.道"
    source = "定义  甲=1   \n如果 真\n  返回 甲\n"
    _did_open(server, uri, source)
    out = server.handle_message(
        _request(
            "textDocument/formatting",
            {"textDocument": {"uri": uri}, "options": {"tabSize": 4, "insertSpaces": True}},
            2,
        )
    )
    edits = _result(out, 2)
    assert len(edits) == 1
    assert edits[0]["range"] == {
        "start": {"line": 0, "character": 0},
        "end": {"line": 3, "character": 0},
    }
    assert edits[0]["newText"] == "定义 甲 = 1\n如果 真\n    返回 甲\n"


def test_formatting_已规范源码不返回编辑():
    server = _server()
    uri = "file:///fmt.道"
    source = "定义 甲 = 1\n"
    _did_open(server, uri, source)
    out = server.handle_message(
        _request("textDocument/formatting", {"textDocument": {"uri": uri}}, 3)
    )
    assert _result(out, 3) == []


def test_formatting_遵循tabSize():
    server = _server()
    uri = "file:///tab.道"
    _did_open(server, uri, "如果 真\n 定义 甲 = 1\n")
    out = server.handle_message(
        _request(
            "textDocument/formatting",
            {"textDocument": {"uri": uri}, "options": {"tabSize": 2}},
            4,
        )
    )
    assert _result(out, 4)[0]["newText"] == "如果 真\n  定义 甲 = 1\n"


def test_formatting_幂等且不破坏字符串():
    server = _server()
    uri = "file:///idem.道"
    source = '定义 文本 = """a   \n  b\n"""\n定义 甲=1\n'
    _did_open(server, uri, source)
    first = _result(
        server.handle_message(
            _request("textDocument/formatting", {"textDocument": {"uri": uri}}, 5)
        ),
        5,
    )[0]["newText"]
    assert '"""a   \n  b\n"""' in first
    _did_open(server, uri, first)
    second = server.handle_message(
        _request("textDocument/formatting", {"textDocument": {"uri": uri}}, 6)
    )
    assert _result(second, 6) == []


# ========================
# prepareRename 边界
# ========================


def test_prepareRename_返回范围与占位文本():
    server = _server()
    uri = "file:///pre.道"
    _did_open(server, uri, "定义 甲 = 1\n打印(甲)\n")
    out = server.handle_message(
        _request(
            "textDocument/prepareRename",
            {"textDocument": {"uri": uri}, "position": {"line": 1, "character": 3}},
            10,
        )
    )
    assert _result(out, 10) == {
        "range": {
            "start": {"line": 1, "character": 3},
            "end": {"line": 1, "character": 4},
        },
        "placeholder": "甲",
    }


def test_prepareRename_空白与越界返回中文错误():
    server = _server()
    uri = "file:///pre.道"
    _did_open(server, uri, "定义 甲 = 1\n")
    for line, character in ((0, 100), (9, 0), (-1, 0)):
        out = server.handle_message(
            _request(
                "textDocument/prepareRename",
                {"textDocument": {"uri": uri}, "position": {"line": line, "character": character}},
                11,
            )
        )
        assert "没有可重命名" in _error(out, 11)["message"]


def test_prepareRename_关键字与内置函数被拒绝():
    server = _server()
    uri = "file:///pre.道"
    _did_open(server, uri, "定义 甲 = 1\n打印(甲)\n")
    keyword = server.handle_message(
        _request(
            "textDocument/prepareRename",
            {"textDocument": {"uri": uri}, "position": {"line": 0, "character": 0}},
            12,
        )
    )
    assert "关键字" in _error(keyword, 12)["message"]
    builtin = server.handle_message(
        _request(
            "textDocument/prepareRename",
            {"textDocument": {"uri": uri}, "position": {"line": 1, "character": 0}},
            13,
        )
    )
    assert "内置函数" in _error(builtin, 13)["message"]


# ========================
# rename
# ========================


def test_rename_单文件返回WorkspaceEdit():
    server = _server()
    uri = "file:///rename.道"
    _did_open(server, uri, "定义 甲 = 1\n打印(甲)\n")
    out = server.handle_message(
        _request(
            "textDocument/rename",
            {
                "textDocument": {"uri": uri},
                "position": {"line": 1, "character": 3},
                "newName": "乙",
            },
            20,
        )
    )
    changes = _result(out, 20)["changes"]
    assert set(changes) == {uri}
    edits = changes[uri]
    assert [edit["range"]["start"]["line"] for edit in edits] == [0, 1]
    assert all(edit["newText"] == "乙" for edit in edits)


def test_rename_非法新名字返回中文错误():
    server = _server()
    uri = "file:///rename.道"
    _did_open(server, uri, "定义 甲 = 1\n")
    cases = (
        {"newName": "123"},
        {"newName": "如果"},
        {},
    )
    for msg_id, extra in enumerate(cases, start=21):
        params = {
            "textDocument": {"uri": uri},
            "position": {"line": 0, "character": 3},
            **extra,
        }
        out = server.handle_message(_request("textDocument/rename", params, msg_id))
        assert "新名字" in _error(out, msg_id)["message"]


def test_rename_不修改字符串与注释(tmp_path):
    server = _server()
    uri = "file:///scope.道"
    source = "定义 甲 = 1\n// 甲 是注释\n定义 文本 = \"甲\"\n打印(甲)\n"
    _did_open(server, uri, source)
    out = server.handle_message(
        _request(
            "textDocument/rename",
            {
                "textDocument": {"uri": uri},
                "position": {"line": 0, "character": 3},
                "newName": "乙",
            },
            30,
        )
    )
    edits = _result(out, 30)["changes"][uri]
    assert [edit["range"]["start"]["line"] for edit in edits] == [0, 3]


def test_rename_跨文件工作区(tmp_path):
    root = tmp_path / "道 项目"
    root.mkdir()
    tool = root / "工具.道"
    main = root / "main.道"
    tool.write_text("导出 辅助\n函数 辅助(值)\n  返回 值\n", encoding="utf-8")
    main_source = "从 工具 导入 辅助\n定义 结果 = 辅助(1)\n辅助(2)\n"
    main.write_text(main_source, encoding="utf-8")

    server = _server()
    _initialize(server, root)
    main_uri = main.as_uri()
    tool_uri = tool.as_uri()
    _did_open(server, main_uri, main_source)

    out = server.handle_message(
        _request(
            "textDocument/rename",
            {
                "textDocument": {"uri": main_uri},
                "position": {"line": 1, "character": 8},
                "newName": "帮手",
            },
            40,
        )
    )
    changes = _result(out, 40)["changes"]
    assert set(changes) == {main_uri, tool_uri}
    assert [edit["range"]["start"]["line"] for edit in changes[main_uri]] == [0, 1, 2]
    assert [edit["range"]["start"]["line"] for edit in changes[tool_uri]] == [0, 1]
    assert all(edit["newText"] == "帮手" for edits in changes.values() for edit in edits)


def test_rename_范围限于工作区(tmp_path):
    root = tmp_path / "项目"
    root.mkdir()
    outside = tmp_path / "外部.道"
    outside.write_text("定义 甲 = 99\n打印(甲)\n", encoding="utf-8")
    main = root / "main.道"
    source = "定义 甲 = 1\n打印(甲)\n"
    main.write_text(source, encoding="utf-8")

    server = _server()
    _initialize(server, root)
    main_uri = main.as_uri()
    _did_open(server, main_uri, source)
    out = server.handle_message(
        _request(
            "textDocument/rename",
            {
                "textDocument": {"uri": main_uri},
                "position": {"line": 1, "character": 3},
                "newName": "乙",
            },
            41,
        )
    )
    assert set(_result(out, 41)["changes"]) == {main_uri}


def test_rename_未初始化工作区时仅当前文档(tmp_path):
    server = _server()
    uri = (tmp_path / "单文件.道").as_uri()
    _did_open(server, uri, "定义 甲 = 1\n打印(甲)\n")
    out = server.handle_message(
        _request(
            "textDocument/rename",
            {
                "textDocument": {"uri": uri},
                "position": {"line": 0, "character": 3},
                "newName": "乙",
            },
            42,
        )
    )
    assert set(_result(out, 42)["changes"]) == {uri}


def test_格式化与重命名经stdio帧流(tmp_path):
    """两类新请求经完整 stdio 帧流仍能正确分派与编解码。"""
    from dao.lsp.protocol import encode_message, read_message

    uri = "file:///flow.道"
    source = "定义  甲=1\n打印(甲)\n"
    incoming = [
        _request("initialize", {}, 1),
        _notify("textDocument/didOpen", {"textDocument": {"uri": uri, "text": source}}),
        _request(
            "textDocument/formatting",
            {"textDocument": {"uri": uri}, "options": {"tabSize": 4}},
            2,
        ),
        _request(
            "textDocument/prepareRename",
            {"textDocument": {"uri": uri}, "position": {"line": 1, "character": 3}},
            3,
        ),
        _request(
            "textDocument/rename",
            {
                "textDocument": {"uri": uri},
                "position": {"line": 1, "character": 3},
                "newName": "乙",
            },
            4,
        ),
        _request("shutdown", {}, 5),
        _notify("exit"),
    ]
    input_stream = io.BytesIO(b"".join(encode_message(msg) for msg in incoming))
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
    assert any(msg.get("id") == 2 and msg.get("result") for msg in sent)
    assert any(
        msg.get("id") == 3 and msg.get("result", {}).get("placeholder") == "甲"
        for msg in sent
    )
    assert any(msg.get("id") == 4 and "changes" in msg.get("result", {}) for msg in sent)
