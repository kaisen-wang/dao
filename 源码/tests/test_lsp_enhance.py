"""道语言 LSP 增强测试。

覆盖：补全前缀过滤（特性层 + 服务器层）、``completionItem/resolve``、
用户自定义声明的悬停签名、控制流语句内的文档符号，以及错误源码与
stdio 帧流下的健壮性。
"""

import io
import os
import sys
from pathlib import Path

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


def _did_open(server, uri, source, version=1):
    return server.handle_message(
        _notify(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": uri,
                    "languageId": "dao",
                    "version": version,
                    "text": source,
                }
            },
        )
    )


def _did_change(server, uri, changes, version):
    """发送一次 didChange；changes 可含 range（增量）或纯 text（全量）。"""
    return server.handle_message(
        _notify(
            "textDocument/didChange",
            {
                "textDocument": {"uri": uri, "version": version},
                "contentChanges": changes,
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


# ========================
# 增量文档同步
# ========================


def test_增量同步_中文与多变更按顺序():
    """两条带 range 的增量变更按 LSP 0-based 坐标依次应用，中文按 code point 计列。"""
    server = _server()
    uri = "file:///inc.道"
    _did_open(server, uri, "定义 甲 = 1\n", version=3)

    # 第 1 条：把第 0 行第 7 列的「1」替换为「2」（BMP 中文与 UTF-16 列一致）。
    # 第 2 条：在第 0 行第 0 列插入一行新的中文声明。
    _did_change(
        server,
        uri,
        [
            {
                "range": {
                    "start": {"line": 0, "character": 7},
                    "end": {"line": 0, "character": 8},
                },
                "text": "2",
            },
            {
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 0, "character": 0},
                },
                "text": "定义 乙 = 9\n",
            },
        ],
        version=4,
    )
    assert server.documents[uri] == "定义 乙 = 9\n定义 甲 = 2\n"
    assert server._versions[uri] == 4


def test_增量同步_全量帧仍兼容():
    """客户端偶发发送无 range 的 Full 帧时整篇替换，仍发布诊断。"""
    server = _server()
    uri = "file:///full.道"
    _did_open(server, uri, "定义 甲 = 1\n")
    out = _did_change(server, uri, [{"text": "定义 = 1\n"}], version=2)
    assert server.documents[uri] == "定义 = 1\n"
    assert any(message.get("method") == "textDocument/publishDiagnostics" for message in out)


def test_增量同步_乱序与重复版本被忽略():
    """旧版本 / 重复版本的变更不覆盖较新文本。"""
    server = _server()
    uri = "file:///order.道"
    _did_open(server, uri, "定义 甲 = 1\n", version=5)

    # 旧版本（4 < 5）应被完全忽略，不产生诊断通知。
    stale = _did_change(server, uri, [{"text": "定义 甲 = 旧\n"}], version=4)
    assert stale == []
    assert server.documents[uri] == "定义 甲 = 1\n"

    # 新版本应用增量编辑。
    _did_change(
        server,
        uri,
        [
            {
                "range": {
                    "start": {"line": 0, "character": 7},
                    "end": {"line": 0, "character": 8},
                },
                "text": "2",
            }
        ],
        version=6,
    )
    assert server.documents[uri] == "定义 甲 = 2\n"

    # 同一版本重复发送也忽略。
    duplicate = _did_change(server, uri, [{"text": "定义 甲 = 重复\n"}], version=6)
    assert duplicate == []
    assert server.documents[uri] == "定义 甲 = 2\n"

    # 关闭后版本记录一并清理。
    server.handle_message(_notify("textDocument/didClose", {"textDocument": {"uri": uri}}))
    assert uri not in server._versions


# ========================
# 跨文件跳转
# ========================


def test_跨文件定义与引用(tmp_path):
    """initialize 带 rootUri（含中文与空格），definition/references 跨文件返回正确 URI 与范围。"""
    # 用含中文与空格的目录名，顺带验证 URI 百分号解码。
    root = tmp_path / "道 项目"
    root.mkdir()
    tool = root / "工具.道"
    main = root / "main.道"
    tool.write_text("导出 辅助\n函数 辅助(值)\n  返回 值\n", encoding="utf-8")
    main_source = "从 工具 导入 辅助\n定义 结果 = 辅助(1)\n辅助(2)\n"
    main.write_text(main_source, encoding="utf-8")

    server = _server()
    caps = _result(
        server.handle_message(
            _request(
                "initialize",
                {"rootUri": root.as_uri(), "capabilities": {}},
                1,
            )
        ),
        1,
    )["capabilities"]
    assert caps["referencesProvider"] is True
    assert server.workspace_roots == [str(root)]

    main_uri = main.as_uri()
    tool_uri = tool.as_uri()
    _did_open(server, main_uri, main_source)

    # 在 import 语句的「辅助」上跳转到工具文件里的函数定义。
    out = server.handle_message(
        _request(
            "textDocument/definition",
            {
                "textDocument": {"uri": main_uri},
                "position": {"line": 0, "character": 8},
            },
            2,
        )
    )
    locations = _result(out, 2)
    assert any(location["uri"] == tool_uri for location in locations)
    assert any(location["range"]["start"]["line"] == 1 for location in locations)

    # references 返回工作区内所有引用（含两个文件的声明处）。
    out = server.handle_message(
        _request(
            "textDocument/references",
            {
                "textDocument": {"uri": main_uri},
                "position": {"line": 1, "character": 8},
                "context": {"includeDeclaration": True},
            },
            3,
        )
    )
    refs = _result(out, 3)
    found = {(ref["uri"], ref["range"]["start"]["line"]) for ref in refs}
    assert {
        (main_uri, 0),
        (main_uri, 1),
        (main_uri, 2),
        (tool_uri, 0),
        (tool_uri, 1),
    } <= found


def test_初始化_workspaceFolders优先于rootUri(tmp_path):
    """workspaceFolders 中的多个根均被记录并解码，优先级高于 rootUri。"""
    server = _server()
    first = tmp_path / "甲"
    second = tmp_path / "乙 目录"
    first.mkdir()
    second.mkdir()
    server.handle_message(
        _request(
            "initialize",
            {
                "rootUri": (tmp_path / "兜底").as_uri(),
                "workspaceFolders": [
                    {"uri": first.as_uri(), "name": "甲"},
                    {"uri": second.as_uri(), "name": "乙"},
                ],
                "capabilities": {},
            },
            1,
        )
    )
    assert server.workspace_roots == [str(first), str(second)]


def test_工作区索引失效后重建(tmp_path):
    """显式失效清空缓存，下次构建反映磁盘上的新源码。"""
    target = tmp_path / "模块.道"
    target.write_text("函数 辅助()\n  返回 1\n", encoding="utf-8")
    first = features.build_workspace_index([str(tmp_path)])
    assert features._WORKSPACE_INDEX is first
    assert any(
        symbol["name"] == "辅助"
        for symbol in first["symbols"][str(target)]
    )

    target.write_text("函数 助手()\n  返回 1\n", encoding="utf-8")
    features.invalidate_workspace_index()
    assert features._WORKSPACE_INDEX is None
    second = features.build_workspace_index([str(tmp_path)])
    assert second is not first
    assert any(
        symbol["name"] == "助手"
        for symbol in second["symbols"][str(target)]
    )


# ========================
# 补全上下文过滤
# ========================


def test_补全上下文过滤_触发字符与作用域():
    """triggerCharacters 已声明；context 透传，局部/参数候选优先且去重。"""
    server = _server()
    caps = _result(server.handle_message(_request("initialize", {}, 1)), 1)["capabilities"]
    assert set(caps["completionProvider"]["triggerCharacters"]) >= {".", "("}

    source = "函数 辅助(参数甲)\n  定义 局部 = 参数甲\n  返回 辅助(局部)\n"
    # 特性层：作用域相关候选排在静态关键字之前，且同名项已去重。
    items = features.completion_list(
        source, context={"triggerKind": 2, "triggerCharacter": "("}
    )["items"]
    labels = [item["label"] for item in items]
    assert len(labels) == len(set(labels))
    assert labels.index("参数甲") < labels.index("函数")
    assert labels.index("局部") < labels.index("函数")
    # 字符触发场景不返回低优先级的文档标识符噪声。
    assert all(item.get("detail") != "文档中的标识符" for item in items)

    # 服务器层：带 context 与前缀的请求按前缀过滤，仍返回标准 CompletionList。
    uri = "file:///ctx.道"
    _did_open(server, uri, source)
    out = server.handle_message(
        _request(
            "textDocument/completion",
            {
                "textDocument": {"uri": uri},
                "position": {"line": 2, "character": 7},
                "context": {"triggerKind": 2, "triggerCharacter": "("},
            },
            60,
        )
    )
    result = _result(out, 60)
    assert result["isIncomplete"] is False
    result_labels = [item["label"] for item in result["items"]]
    assert result_labels
    assert all(label.startswith("辅") for label in result_labels)
    assert "辅助" in result_labels

