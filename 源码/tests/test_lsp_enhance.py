"""道语言 LSP 增强测试。

覆盖：补全前缀过滤（特性层 + 服务器层）、``completionItem/resolve``、
用户自定义声明的悬停签名、控制流语句内的文档符号，以及错误源码与
stdio 帧流下的健壮性。
"""

import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.lsp import LanguageServer, features
from dao.lsp.protocol import encode_message, read_message


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
# 补全前缀过滤
# ========================


def test_词前缀提取():
    """只取词首到光标的子串；空白、标点与越界返回空串。"""
    assert features.word_prefix_at("打印(1)", 0, 1) == "打"
    assert features.word_prefix_at("打印(1)", 0, 2) == "打印"
    assert features.word_prefix_at("打印(1)", 0, 0) == ""
    assert features.word_prefix_at("打印(1)", 0, 3) == ""
    assert features.word_prefix_at("", 0, 0) == ""
    assert features.word_prefix_at("打印", 5, 0) == ""
    assert features.word_prefix_at("打印", 0, -1) == ""


def test_补全前缀过滤_特性层():
    """带前缀时仅返回 label 以该前缀开头的候选；无前缀仍返回全量。"""
    all_items = features.completion_list("")["items"]
    assert any(item["label"] == "函数" for item in all_items)

    items = features.completion_list("", "打")["items"]
    assert items
    assert all(item["label"].startswith("打") for item in items)
    assert any(item["label"] == "打印" for item in items)

    source = "定义 我的变量 = 1\n"
    assert {
        item["label"] for item in features.completion_list(source, "我的")["items"]
    } == {"我的变量"}
    assert features.completion_list(source, "不存在的前缀")["items"] == []


def test_补全前缀过滤_服务器层():
    """completion 请求按 position 处的词前缀过滤，返回类型仍是 CompletionList。"""
    server = _server()
    uri = "file:///c.道"
    _did_open(server, uri, "定义 甲 = 1\n打印(甲)\n")

    out = server.handle_message(
        _request(
            "textDocument/completion",
            {"textDocument": {"uri": uri}, "position": {"line": 1, "character": 2}},
            20,
        )
    )
    result = _result(out, 20)
    assert result["isIncomplete"] is False
    labels = {item["label"] for item in result["items"]}
    assert labels and all(label.startswith("打") for label in labels)

    # 光标落在词首（前缀为空）时仍返回全量候选。
    out2 = server.handle_message(
        _request(
            "textDocument/completion",
            {"textDocument": {"uri": uri}, "position": {"line": 0, "character": 0}},
            21,
        )
    )
    assert any(item["label"] == "函数" for item in _result(out2, 21)["items"])


# ========================
# completionItem/resolve
# ========================


def test_completion_resolve_声明与回填():
    """capabilities 声明 resolveProvider，resolve 回填详情且保留已有字段。"""
    server = _server()
    caps = _result(
        server.handle_message(_request("initialize", {}, 30)), 30
    )["capabilities"]
    assert caps["completionProvider"]["resolveProvider"] is True

    resolved = features.completion_resolve({"label": "打印"})
    assert resolved["detail"] == "内置函数"
    assert "控制台" in resolved["documentation"]

    out = server.handle_message(
        _request("completionItem/resolve", {"label": "函数"}, 31)
    )
    item = _result(out, 31)
    assert "关键字" in item["detail"]
    assert item["kind"] == 14

    # 已存在字段不被覆盖；未知标签与非法输入安全返回。
    assert features.completion_resolve({"label": "打印", "detail": "自定义"})[
        "detail"
    ] == "自定义"
    assert features.completion_resolve({"label": "未知符号"}) == {"label": "未知符号"}
    assert features.completion_resolve([]) == {}


# ========================
# 悬停增强
# ========================


def test_悬停用户函数签名():
    """悬停用户函数显示签名（含默认参数），关键字仍优先于用户符号。"""
    source = "函数 问候(名字, 次数=1)\n  返回 名字\n"
    hover = features.hover_info(source, 0, 4)
    assert hover is not None
    text = hover["contents"]["value"]
    assert "**问候**（函数）" in text
    assert "问候(名字, 次数=...)" in text

    # 同名用户函数不覆盖关键字说明。
    keyword = features.hover_info("函数 甲()\n  返回 1\n", 0, 0)
    assert keyword is not None and "关键字" in keyword["contents"]["value"]


def test_悬停用户类与方法():
    """类声明显示类型签名，递归收集到的方法也能按名字悬停。"""
    source = (
        "类型 人\n"
        '  定义 名字 = "张三"\n'
        "  函数 打招呼(其他)\n"
        "    返回 其他\n"
    )
    cls = features.hover_info(source, 0, 3)
    assert cls is not None
    assert "**人**（类型）" in cls["contents"]["value"]
    assert "类型 人" in cls["contents"]["value"]

    method = features.hover_info(source, 2, 5)
    assert method is not None
    text = method["contents"]["value"]
    assert "**打招呼**（函数）" in text
    assert "打招呼(其他)" in text


def test_悬停静态优先与健壮性():
    """内置函数仍给出中文说明；错误源码与空白位置不抛异常。"""
    builtin = features.hover_info("  打印(1)\n", 0, 3)
    assert builtin is not None and "内置函数" in builtin["contents"]["value"]
    for source in ("@@@\n", "", "   \n"):
        assert features.hover_info(source, 0, 0) is None
    for bad in ("定义 = ", "函数 (\n", '定义 未闭合 = "abc\n'):
        hover = features.hover_info(bad, 0, 0)
        assert hover is None or isinstance(hover, dict)


# ========================
# 文档符号覆盖增强
# ========================


def test_文档符号覆盖控制流声明():
    """如果/否则/当/遍历/匹配分支内的声明都进入大纲。"""
    source = (
        "如果 真\n"
        "  定义 分支变量 = 1\n"
        "否则\n"
        "  定义 否则变量 = 2\n"
        "当 真\n"
        "  定义 循环变量 = 3\n"
        "遍历 项 在 [1]\n"
        "  定义 遍历变量 = 4\n"
        "匹配 1\n"
        " 情况 1\n"
        "  定义 情况变量 = 5\n"
    )
    symbols = features.document_symbols(source)
    names = {symbol["name"] for symbol in symbols}
    assert {"分支变量", "否则变量", "循环变量", "遍历变量", "情况变量"} <= names

    # 经服务器链路同样可见。
    server = _server()
    uri = "file:///s.道"
    _did_open(server, uri, source)
    out = server.handle_message(
        _request("textDocument/documentSymbol", {"textDocument": {"uri": uri}}, 40)
    )
    assert "分支变量" in {symbol["name"] for symbol in _result(out, 40)}


# ========================
# 健壮性 / 集成
# ========================


def test_增强特性错误源码不崩溃():
    """各类错误源码下新增特性都返回可用结果且不抛异常。"""
    for source in (
        "",
        "定义 = ",
        "函数 (\n",
        "@@@\n",
        "如果\n",
        '定义 未闭合 = "abc\n',
    ):
        assert isinstance(features.completion_list(source, "定")["items"], list)
        assert isinstance(features.completion_resolve({"label": "打印"}), dict)
        assert isinstance(features.document_symbols(source), list)
        assert isinstance(features._user_symbols(source), dict)

    server = _server()
    uri = "file:///bad.道"
    _did_open(server, uri, "定义 = @\n")
    for msg_id, method in enumerate(
        ("textDocument/completion", "completionItem/resolve", "textDocument/hover"),
        start=50,
    ):
        out = server.handle_message(
            _request(method, {"label": "打印"}, msg_id)
        )
        assert any("result" in message for message in out), method
        assert not any("error" in message for message in out), method


def test_增强特性经stdio帧流():
    """用内存帧流驱动 serve()，验证新增请求可正确编解码并分派。"""
    uri = "file:///e.道"
    source = "函数 问候(名字)\n  返回 名字\n"
    incoming = [
        _request("initialize", {}, 1),
        _notify("textDocument/didOpen", {"textDocument": {"uri": uri, "text": source}}),
        _request(
            "textDocument/completion",
            {"textDocument": {"uri": uri}, "position": {"line": 0, "character": 0}},
            2,
        ),
        _request("completionItem/resolve", {"label": "打印"}, 3),
        _request(
            "textDocument/hover",
            {"textDocument": {"uri": uri}, "position": {"line": 0, "character": 4}},
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
    assert any(msg.get("id") == 1 and "capabilities" in msg.get("result", {}) for msg in sent)
    assert any(msg.get("id") == 2 and "items" in msg.get("result", {}) for msg in sent)
    assert any(
        msg.get("id") == 3 and "内置函数" in msg.get("result", {}).get("detail", "")
        for msg in sent
    )
    assert any(msg.get("id") == 4 and "问候" in str(msg.get("result")) for msg in sent)
    assert any(msg.get("id") == 5 for msg in sent)
