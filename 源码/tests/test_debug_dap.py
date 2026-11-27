"""
DAP（Debug Adapter Protocol）适配器测试
========================================

覆盖：JSON 帧编码/解码/残帧/异常、initialize、setBreakpoints、launch、
configurationDone、threads、stackTrace、scopes、variables、evaluate、
continue、next、stepIn、stepOut、disconnect、断点命中与程序输出转发。
"""

from __future__ import annotations

import time
from io import BytesIO

import pytest

from dao.debug.dap import (
    DAP帧错误,
    DAP消息流,
    DAP适配器,
    SUPPORTED_COMMANDS,
    编码消息,
    解码消息,
)

程序源码 = "定义 a = 1\n打印(a)\n定义 b = a + 2\n打印(b)\n"
函数源码 = "函数 加一(x)\n    返回 x + 1\n定义 a = 2\n定义 b = 加一(a)\n打印(b)\n"
循环源码 = "定义 i = 0\n当 i < 3\n    打印(i)\n    设 i = i + 1\n"
捕获异常源码 = "尝试\n    抛出(\"出错了\")\n捕获 e\n    打印(\"已捕获\")\n"
未捕获异常源码 = "定义 a = 1\n抛出(\"未捕获\")\n打印(a)\n"
常量源码 = "常量 c = 7\n打印(c)\n"
列表源码 = "定义 a = [1, 2, 3]\n打印(a)\n"


def 写程序(tmp_path, 源码=程序源码, 名称="demo.道"):
    路径 = tmp_path / 名称
    路径.write_text(源码, encoding="utf-8")
    return str(路径)


def 请求(适配器, 命令, 序号=1, **参数):
    适配器.处理消息(
        {"seq": 序号, "type": "request", "command": 命令, "arguments": 参数}
    )


def 消息列表(输出: BytesIO):
    消息, 余量 = 解码消息(输出.getvalue())
    assert 余量 == b"", "输出中存在未解析的残缺帧"
    return 消息


def 响应(输出: BytesIO, 命令: str, 请求序号: int | None = None):
    return next(
        m
        for m in 消息列表(输出)
        if m.get("type") == "response"
        and m.get("command") == 命令
        and (请求序号 is None or m.get("request_seq") == 请求序号)
    )


def 事件(输出: BytesIO, 名称: str):
    return [
        m
        for m in 消息列表(输出)
        if m.get("type") == "event" and m.get("event") == 名称
    ]


def 等待(条件, 超时=3.0):
    截止 = time.monotonic() + 超时
    while time.monotonic() < 截止:
        if 条件():
            return True
        time.sleep(0.005)
    return False


@pytest.fixture
def 新建适配器():
    实例列表 = []

    def 工厂():
        输出 = BytesIO()
        适配器 = DAP适配器(BytesIO(), 输出)
        适配器.输出 = 输出
        实例列表.append(适配器)
        return 适配器

    yield 工厂
    for 适配器 in 实例列表:
        if 适配器.执行线程 is not None:
            适配器.执行线程.join(timeout=3)
        适配器.已连接 = False
        适配器.恢复事件.set()


# ---------------- 帧解析 ----------------
def test_帧编码解码往返():
    消息 = {"seq": 1, "type": "request", "command": "initialize", "arguments": {}}
    帧 = 编码消息(消息)
    assert 帧.startswith(b"Content-Length: ")
    assert b"\r\n\r\n" in 帧
    解析结果, 余量 = 解码消息(帧)
    assert 解析结果 == [消息]
    assert 余量 == b""


def test_解码多帧与残帧():
    帧1 = 编码消息({"seq": 1, "type": "request", "command": "threads"})
    帧2 = 编码消息({"seq": 2, "type": "request", "command": "disconnect"})
    完整帧3 = 编码消息({"seq": 3, "type": "request", "command": "continue"})
    半帧 = 完整帧3[: len(完整帧3) // 2]
    消息, 余量 = 解码消息(帧1 + 帧2 + 半帧)
    assert [m["command"] for m in 消息] == ["threads", "disconnect"]
    assert 余量 == 半帧
    后续, 余量2 = 解码消息(余量 + 完整帧3[len(半帧):])
    assert 后续[0]["command"] == "continue" and 余量2 == b""


def test_解码大小写不敏感且容忍额外头():
    正文 = b'{"seq": 9, "type": "request", "command": "threads"}'
    帧 = b"content-length: " + str(len(正文)).encode() + b"\r\nContent-Type: application/vscode-jsonrpc\r\n\r\n" + 正文
    消息, 余量 = 解码消息(帧)
    assert 消息[0]["seq"] == 9 and 余量 == b""


def test_解码非法帧抛出异常():
    with pytest.raises(DAP帧错误):
        解码消息(b"Content-Type: application/json\r\n\r\n{}")
    with pytest.raises(DAP帧错误):
        解码消息(b"Content-Length: 1\r\n\r\n{")
    with pytest.raises(DAP帧错误):
        解码消息(b"Content-Length: abc\r\n\r\n{}")


class 分块读取器:
    def __init__(self, 数据: bytes, 块长: int = 3):
        self.数据 = 数据
        self.块长 = 块长

    def read(self, _):
        if not self.数据:
            return b""
        块, self.数据 = self.数据[: self.块长], self.数据[self.块长:]
        return 块


def test_消息流分块读取与发送():
    数据 = 编码消息({"seq": 1, "type": "request", "command": "initialize"}) + 编码消息(
        {"seq": 2, "type": "request", "command": "threads"}
    )
    输出 = BytesIO()
    流 = DAP消息流(分块读取器(数据), 输出)
    assert 流.读取消息()["command"] == "initialize"
    assert 流.读取消息()["command"] == "threads"
    assert 流.读取消息() is None
    流.发送消息({"seq": 8, "type": "event", "event": "initialized"})
    解析结果, _ = 解码消息(输出.getvalue())
    assert 解析结果[0]["event"] == "initialized"


# ---------------- 请求响应 ----------------
def test_initialize响应能力并发送初始化事件(新建适配器):
    适配器 = 新建适配器()
    请求(适配器, "initialize", 7)
    响应消息 = 响应(适配器.输出, "initialize")
    assert 响应消息["request_seq"] == 7 and 响应消息["success"] is True
    assert 响应消息["body"]["supportsConfigurationDoneRequest"] is True
    assert 响应消息["body"]["supportsEvaluateForHovers"] is True
    assert len(事件(适配器.输出, "initialized")) == 1


def test_setBreakpoints同步到调试器(新建适配器, tmp_path):
    路径 = 写程序(tmp_path, 程序源码 + "打印(1)\n", "断点.道")
    适配器 = 新建适配器()
    请求(
        适配器,
        "setBreakpoints",
        4,
        source={"path": 路径},
        breakpoints=[{"line": 2}, {"line": 5}, {"line": 0}],
    )
    正文 = 响应(适配器.输出, "setBreakpoints", 4)["body"]
    assert [bp["line"] for bp in 正文["breakpoints"]] == [2, 5, 0]
    assert all(bp["verified"] for bp in 正文["breakpoints"][:2])
    assert 正文["breakpoints"][2]["verified"] is False
    assert 正文["breakpoints"][2]["reason"]
    assert {(bp.文件, bp.行号) for bp in 适配器.debugger.列出断点()} == {
        (路径, 2),
        (路径, 5),
    }
    # 再次设置为空列表应清除该文件的断点
    请求(
        适配器,
        "setBreakpoints",
        5,
        source={"path": 路径},
        breakpoints=[],
    )
    assert 适配器.debugger.列出断点() == []


def test_launch缺少program返回失败(新建适配器):
    适配器 = 新建适配器()
    请求(适配器, "launch", 3)
    响应消息 = 响应(适配器.输出, "launch")
    assert 响应消息["success"] is False
    assert "program" in 响应消息["message"]


def test_threads与configurationDone响应(新建适配器):
    适配器 = 新建适配器()
    请求(适配器, "initialize", 1)
    请求(适配器, "configurationDone", 2)
    响应消息 = 响应(适配器.输出, "configurationDone")
    assert 响应消息["success"] is True
    请求(适配器, "threads", 3)
    threads = 响应(适配器.输出, "threads")["body"]["threads"]
    assert threads == [{"id": 1, "name": "主线程"}]


def test_未知命令返回失败(新建适配器):
    适配器 = 新建适配器()
    请求(适配器, "notARealCommand", 11)
    响应消息 = 响应(适配器.输出, "notARealCommand")
    assert 响应消息["success"] is False
    assert "不支持" in 响应消息["message"]
    assert "evaluate" in SUPPORTED_COMMANDS


def test_disconnect结束主循环(新建适配器):
    适配器 = 新建适配器()
    输入 = BytesIO(编码消息({"seq": 1, "type": "request", "command": "disconnect"}))
    适配器.流.reader = 输入
    适配器.run()
    assert 适配器.已连接 is False
    assert 响应(适配器.输出, "disconnect")["success"] is True


# ---------------- 断点命中与执行控制 ----------------
def test_断点命中栈帧变量与继续执行(新建适配器, tmp_path):
    路径 = 写程序(tmp_path)
    适配器 = 新建适配器()
    请求(适配器, "initialize", 1)
    请求(适配器, "setBreakpoints", 2, source={"path": 路径}, breakpoints=[{"line": 3}])
    请求(适配器, "launch", 3, program=路径)
    请求(适配器, "configurationDone", 4)
    assert 等待(lambda: 适配器.暂停事件 is not None)

    停止事件 = 事件(适配器.输出, "stopped")
    assert len(停止事件) == 1
    assert 停止事件[0]["body"]["reason"] == "breakpoint"
    assert 停止事件[0]["body"]["threadId"] == 1

    请求(适配器, "stackTrace", 5)
    栈帧 = 响应(适配器.输出, "stackTrace")["body"]["stackFrames"]
    assert 栈帧[0]["line"] == 3
    assert 栈帧[0]["source"]["path"] == 路径

    请求(适配器, "scopes", 6)
    作用域 = 响应(适配器.输出, "scopes")["body"]["scopes"]
    assert 作用域[0]["name"] == "局部变量"
    assert 作用域[0]["variablesReference"] == 1

    请求(适配器, "variables", 7, variablesReference=1)
    变量 = {v["name"]: v["value"] for v in 响应(适配器.输出, "variables")["body"]["variables"]}
    assert 变量["a"] == "1"

    输出事件 = 事件(适配器.输出, "output")
    assert any("1" in e["body"]["output"] for e in 输出事件)

    请求(适配器, "continue", 8, threadId=1)
    assert 适配器.执行线程.join(timeout=3) is None
    assert not 适配器.执行线程.is_alive()
    assert 事件(适配器.输出, "continued")
    assert 事件(适配器.输出, "terminated")
    assert 事件(适配器.输出, "exited")[0]["body"]["exitCode"] == 0


def test_evaluate表达式与失败分支(新建适配器, tmp_path):
    路径 = 写程序(tmp_path)
    适配器 = 新建适配器()
    request_args = dict(source={"path": 路径}, breakpoints=[{"line": 3}])
    请求(适配器, "initialize", 1)
    请求(适配器, "setBreakpoints", 2, **request_args)
    请求(适配器, "launch", 3, program=路径)
    请求(适配器, "configurationDone", 4)
    assert 等待(lambda: 适配器.暂停事件 is not None)

    请求(适配器, "evaluate", 5, expression="a + 2", context="watch")
    求值 = 响应(适配器.输出, "evaluate", 5)
    assert 求值["success"] is True
    assert 求值["body"]["result"] == "3"

    请求(适配器, "evaluate", 6, expression="不存在的变量")
    assert 响应(适配器.输出, "evaluate", 6)["success"] is False
    请求(适配器, "continue", 7)
    适配器.执行线程.join(timeout=3)


def test_next单步跳过函数调用(新建适配器, tmp_path):
    路径 = 写程序(tmp_path, 函数源码, "函数.道")
    适配器 = 新建适配器()
    请求(适配器, "initialize", 1)
    请求(适配器, "setBreakpoints", 2, source={"path": 路径}, breakpoints=[{"line": 4}])
    请求(适配器, "launch", 3, program=路径)
    请求(适配器, "configurationDone", 4)
    assert 等待(lambda: 适配器.暂停事件 is not None)
    assert 适配器.暂停事件.行号 == 4

    请求(适配器, "next", 5, threadId=1)
    # 步过函数调用：跳过函数体（第 2 行），直接停在第 5 行
    assert 等待(lambda: 适配器.暂停事件 is not None and 适配器.暂停事件.行号 == 5)
    assert 适配器.停止原因 == "step"
    assert len(适配器.暂停事件.调用栈) == 0
    请求(适配器, "continue", 6)
    适配器.执行线程.join(timeout=3)


def test_stepIn进入函数体(新建适配器, tmp_path):
    路径 = 写程序(tmp_path, 函数源码, "步入.道")
    适配器 = 新建适配器()
    请求(适配器, "initialize", 1)
    请求(适配器, "setBreakpoints", 2, source={"path": 路径}, breakpoints=[{"line": 4}])
    请求(适配器, "launch", 3, program=路径)
    请求(适配器, "configurationDone", 4)
    assert 等待(lambda: 适配器.暂停事件 is not None)

    请求(适配器, "stepIn", 5, threadId=1)
    assert 等待(lambda: 适配器.暂停事件 is not None and len(适配器.暂停事件.调用栈) > 0)
    assert 适配器.暂停事件.行号 == 2
    请求(适配器, "continue", 6)
    适配器.执行线程.join(timeout=3)


def test_stepOut返回调用者(新建适配器, tmp_path):
    路径 = 写程序(tmp_path, 函数源码, "步出.道")
    适配器 = 新建适配器()
    请求(适配器, "initialize", 1)
    请求(适配器, "setBreakpoints", 2, source={"path": 路径}, breakpoints=[{"line": 2}])
    请求(适配器, "launch", 3, program=路径)
    请求(适配器, "configurationDone", 4)
    assert 等待(lambda: 适配器.暂停事件 is not None)
    assert len(适配器.暂停事件.调用栈) == 1

    请求(适配器, "stepOut", 5, threadId=1)
    assert 等待(lambda: 适配器.暂停事件 is not None and len(适配器.暂停事件.调用栈) == 0)
    assert 适配器.暂停事件.行号 == 5
    请求(适配器, "continue", 6)
    适配器.执行线程.join(timeout=3)


def test_stopOnEntry在首语句暂停(新建适配器, tmp_path):
    路径 = 写程序(tmp_path)
    适配器 = 新建适配器()
    请求(适配器, "initialize", 1)
    请求(适配器, "launch", 2, program=路径, stopOnEntry=True)
    请求(适配器, "configurationDone", 3)
    assert 等待(lambda: 适配器.暂停事件 is not None)
    assert 适配器.停止原因 == "entry"
    assert 适配器.暂停事件.行号 == 1
    请求(适配器, "continue", 4)
    适配器.执行线程.join(timeout=3)


def test_disconnect释放暂停的程序(新建适配器, tmp_path):
    路径 = 写程序(tmp_path)
    适配器 = 新建适配器()
    请求(适配器, "initialize", 1)
    请求(适配器, "setBreakpoints", 2, source={"path": 路径}, breakpoints=[{"line": 2}])
    请求(适配器, "launch", 3, program=路径)
    请求(适配器, "configurationDone", 4)
    assert 等待(lambda: 适配器.暂停事件 is not None)
    请求(适配器, "disconnect", 5)
    assert 适配器.已连接 is False
    适配器.执行线程.join(timeout=3)
    assert not 适配器.执行线程.is_alive()


def test_noDebug模式不暂停直接结束(新建适配器, tmp_path):
    路径 = 写程序(tmp_path)
    适配器 = 新建适配器()
    请求(适配器, "initialize", 1)
    请求(适配器, "setBreakpoints", 2, source={"path": 路径}, breakpoints=[{"line": 2}])
    请求(适配器, "launch", 3, program=路径, noDebug=True)
    请求(适配器, "configurationDone", 4)
    assert 适配器.执行线程.join(timeout=3) is None
    assert 适配器.暂停事件 is None
    assert 事件(适配器.输出, "stopped") == []
    assert 事件(适配器.输出, "terminated")


# ---------------- 条件断点 ----------------
def test_initialize声明条件断点与变量写入能力(新建适配器):
    适配器 = 新建适配器()
    请求(适配器, "initialize", 1)
    能力 = 响应(适配器.输出, "initialize")["body"]
    assert 能力["supportsConditionalBreakpoints"] is True
    assert 能力["supportsHitConditionalBreakpoints"] is True
    assert 能力["supportsSetVariable"] is True
    assert {f["filter"] for f in 能力["exceptionBreakpointFilters"]} == {
        "raised",
        "uncaught",
    }


def test_条件断点仅条件为真时暂停(新建适配器, tmp_path):
    路径 = 写程序(tmp_path)
    适配器 = 新建适配器()
    请求(适配器, "initialize", 1)
    请求(
        适配器,
        "setBreakpoints",
        2,
        source={"path": 路径},
        breakpoints=[
            {"line": 3, "condition": "a == 2"},  # 为假：不应暂停
            {"line": 4, "condition": "b == 3"},  # 为真：应暂停
        ],
    )
    请求(适配器, "launch", 3, program=路径)
    请求(适配器, "configurationDone", 4)
    assert 等待(lambda: 适配器.暂停事件 is not None)
    assert 适配器.暂停事件.行号 == 4
    assert len(事件(适配器.输出, "stopped")) == 1
    assert 事件(适配器.输出, "stopped")[0]["body"]["reason"] == "breakpoint"
    请求(适配器, "continue", 5)
    适配器.执行线程.join(timeout=3)


def test_条件断点语法错误给出中文提示(新建适配器, tmp_path):
    路径 = 写程序(tmp_path)
    适配器 = 新建适配器()
    请求(适配器, "initialize", 1)
    请求(
        适配器,
        "setBreakpoints",
        2,
        source={"path": 路径},
        breakpoints=[{"line": 3, "condition": "a +"}],
    )
    请求(适配器, "launch", 3, program=路径)
    请求(适配器, "configurationDone", 4)
    assert 适配器.执行线程.join(timeout=3) is None
    assert 事件(适配器.输出, "stopped") == []
    错误输出 = [e["body"]["output"] for e in 事件(适配器.输出, "output")]
    assert any("断点条件语法或求值错误" in 文本 for 文本 in 错误输出)


# ---------------- 命中次数条件 ----------------
def test_hitCondition数字在第二次命中暂停(新建适配器, tmp_path):
    路径 = 写程序(tmp_path, 循环源码, "循环.道")
    适配器 = 新建适配器()
    请求(适配器, "initialize", 1)
    请求(
        适配器,
        "setBreakpoints",
        2,
        source={"path": 路径},
        breakpoints=[{"line": 3, "hitCondition": "2"}],
    )
    请求(适配器, "launch", 3, program=路径)
    请求(适配器, "configurationDone", 4)
    assert 等待(lambda: 适配器.暂停事件 is not None)
    请求(适配器, "evaluate", 5, expression="i")
    assert 响应(适配器.输出, "evaluate", 5)["body"]["result"] == "1"
    请求(适配器, "continue", 6)
    适配器.执行线程.join(timeout=3)
    assert len(事件(适配器.输出, "stopped")) == 1


def test_hitCondition比较表达式(新建适配器, tmp_path):
    路径 = 写程序(tmp_path, 循环源码, "循环比较.道")
    适配器 = 新建适配器()
    请求(适配器, "initialize", 1)
    请求(
        适配器,
        "setBreakpoints",
        2,
        source={"path": 路径},
        breakpoints=[{"line": 3, "hitCondition": ">= 3"}],
    )
    请求(适配器, "launch", 3, program=路径)
    请求(适配器, "configurationDone", 4)
    assert 等待(lambda: 适配器.暂停事件 is not None)
    请求(适配器, "evaluate", 5, expression="i")
    assert 响应(适配器.输出, "evaluate", 5)["body"]["result"] == "2"
    请求(适配器, "continue", 6)
    适配器.执行线程.join(timeout=3)


def test_hitCondition不支持时给出中文提示(新建适配器, tmp_path):
    路径 = 写程序(tmp_path, 循环源码, "循环非法.道")
    适配器 = 新建适配器()
    请求(适配器, "initialize", 1)
    请求(
        适配器,
        "setBreakpoints",
        2,
        source={"path": 路径},
        breakpoints=[{"line": 3, "hitCondition": "随便写"}],
    )
    请求(适配器, "launch", 3, program=路径)
    请求(适配器, "configurationDone", 4)
    assert 适配器.执行线程.join(timeout=3) is None
    assert 事件(适配器.输出, "stopped") == []
    错误输出 = [e["body"]["output"] for e in 事件(适配器.输出, "output")]
    assert any("不支持的命中次数条件" in 文本 for 文本 in 错误输出)


# ---------------- 变量写入 ----------------
def test_setVariable修改局部变量并影响执行(新建适配器, tmp_path):
    路径 = 写程序(tmp_path)
    适配器 = 新建适配器()
    请求(适配器, "initialize", 1)
    请求(适配器, "setBreakpoints", 2, source={"path": 路径}, breakpoints=[{"line": 2}])
    请求(适配器, "launch", 3, program=路径)
    请求(适配器, "configurationDone", 4)
    assert 等待(lambda: 适配器.暂停事件 is not None)
    请求(适配器, "setVariable", 5, variablesReference=1, name="a", value="10")
    结果 = 响应(适配器.输出, "setVariable", 5)
    assert 结果["success"] is True
    assert 结果["body"]["value"] == "10"
    请求(适配器, "continue", 6)
    适配器.执行线程.join(timeout=3)
    assert any("10" in e["body"]["output"] for e in 事件(适配器.输出, "output"))


def test_setVariable写入不存在的变量报中文错误(新建适配器, tmp_path):
    路径 = 写程序(tmp_path)
    适配器 = 新建适配器()
    请求(适配器, "initialize", 1)
    请求(适配器, "setBreakpoints", 2, source={"path": 路径}, breakpoints=[{"line": 2}])
    请求(适配器, "launch", 3, program=路径)
    请求(适配器, "configurationDone", 4)
    assert 等待(lambda: 适配器.暂停事件 is not None)
    请求(适配器, "setVariable", 5, variablesReference=1, name="不存在", value="1")
    结果 = 响应(适配器.输出, "setVariable", 5)
    assert 结果["success"] is False
    assert "不存在" in 结果["message"]
    请求(适配器, "continue", 6)
    适配器.执行线程.join(timeout=3)


def test_setVariable写入常量报中文错误(新建适配器, tmp_path):
    路径 = 写程序(tmp_path, 常量源码, "常量.道")
    适配器 = 新建适配器()
    请求(适配器, "initialize", 1)
    请求(适配器, "setBreakpoints", 2, source={"path": 路径}, breakpoints=[{"line": 2}])
    请求(适配器, "launch", 3, program=路径)
    请求(适配器, "configurationDone", 4)
    assert 等待(lambda: 适配器.暂停事件 is not None)
    请求(适配器, "setVariable", 5, variablesReference=1, name="c", value="2")
    结果 = 响应(适配器.输出, "setVariable", 5)
    assert 结果["success"] is False
    assert "不可写" in 结果["message"] and "常量" in 结果["message"]
    请求(适配器, "continue", 6)
    适配器.执行线程.join(timeout=3)


def test_setVariable写入列表元素(新建适配器, tmp_path):
    路径 = 写程序(tmp_path, 列表源码, "列表.道")
    适配器 = 新建适配器()
    请求(适配器, "initialize", 1)
    请求(适配器, "setBreakpoints", 2, source={"path": 路径}, breakpoints=[{"line": 2}])
    请求(适配器, "launch", 3, program=路径)
    请求(适配器, "configurationDone", 4)
    assert 等待(lambda: 适配器.暂停事件 is not None)
    请求(适配器, "variables", 5, variablesReference=1)
    变量 = 响应(适配器.输出, "variables", 5)["body"]["variables"]
    引用 = next(v["variablesReference"] for v in 变量 if v["name"] == "a")
    assert 引用 > 0
    请求(适配器, "setVariable", 6, variablesReference=引用, name="0", value="9")
    assert 响应(适配器.输出, "setVariable", 6)["success"] is True
    请求(适配器, "evaluate", 7, expression="a[0]")
    assert 响应(适配器.输出, "evaluate", 7)["body"]["result"] == "9"
    请求(适配器, "continue", 8)
    适配器.执行线程.join(timeout=3)


# ---------------- 异常断点 ----------------
def test_异常断点raised过滤器暂停(新建适配器, tmp_path):
    路径 = 写程序(tmp_path, 捕获异常源码, "异常.道")
    适配器 = 新建适配器()
    请求(适配器, "initialize", 1)
    请求(适配器, "setExceptionBreakpoints", 2, filters=["raised"])
    请求(适配器, "launch", 3, program=路径)
    请求(适配器, "configurationDone", 4)
    assert 等待(lambda: 适配器.暂停事件 is not None)
    assert 适配器.停止原因 == "exception"
    assert 事件(适配器.输出, "stopped")[0]["body"]["reason"] == "exception"
    请求(适配器, "continue", 5)
    适配器.执行线程.join(timeout=3)
    assert any("已捕获" in e["body"]["output"] for e in 事件(适配器.输出, "output"))


def test_异常断点uncaught过滤器跳过已捕获异常(新建适配器, tmp_path):
    路径 = 写程序(tmp_path, 捕获异常源码, "异常跳过.道")
    适配器 = 新建适配器()
    请求(适配器, "initialize", 1)
    请求(适配器, "setExceptionBreakpoints", 2, filters=["uncaught"])
    请求(适配器, "launch", 3, program=路径)
    请求(适配器, "configurationDone", 4)
    assert 适配器.执行线程.join(timeout=3) is None
    assert 事件(适配器.输出, "stopped") == []
    assert any("已捕获" in e["body"]["output"] for e in 事件(适配器.输出, "output"))


def test_异常断点uncaught过滤器命中未捕获异常(新建适配器, tmp_path):
    路径 = 写程序(tmp_path, 未捕获异常源码, "未捕获.道")
    适配器 = 新建适配器()
    请求(适配器, "initialize", 1)
    请求(适配器, "setExceptionBreakpoints", 2, filters=["uncaught"])
    请求(适配器, "launch", 3, program=路径)
    请求(适配器, "configurationDone", 4)
    assert 等待(lambda: 适配器.暂停事件 is not None)
    assert 适配器.停止原因 == "exception"
    assert 事件(适配器.输出, "stopped")[0]["body"]["reason"] == "exception"
    请求(适配器, "continue", 5)
    适配器.执行线程.join(timeout=3)
    assert 适配器.异常退出 is True


def test_异常断点无过滤器不暂停(新建适配器, tmp_path):
    路径 = 写程序(tmp_path, 捕获异常源码, "异常空.道")
    适配器 = 新建适配器()
    请求(适配器, "initialize", 1)
    请求(适配器, "setExceptionBreakpoints", 2, filters=[])
    请求(适配器, "launch", 3, program=路径)
    请求(适配器, "configurationDone", 4)
    assert 适配器.执行线程.join(timeout=3) is None
    assert 事件(适配器.输出, "stopped") == []


# ---------------- 断点源码映射 ----------------
def test_setBreakpoints不存在文件返回未验证(新建适配器, tmp_path):
    不存在 = str(tmp_path / "不存在.道")
    适配器 = 新建适配器()
    请求(适配器, "setBreakpoints", 1, source={"path": 不存在}, breakpoints=[{"line": 2}])
    条目 = 响应(适配器.输出, "setBreakpoints", 1)["body"]["breakpoints"][0]
    assert 条目["verified"] is False
    assert "不存在" in 条目["reason"]
    assert 适配器.debugger.列出断点() == []


def test_setBreakpoints超出行数返回未验证(新建适配器, tmp_path):
    路径 = 写程序(tmp_path)  # 4 行
    适配器 = 新建适配器()
    请求(适配器, "setBreakpoints", 1, source={"path": 路径}, breakpoints=[{"line": 999}])
    条目 = 响应(适配器.输出, "setBreakpoints", 1)["body"]["breakpoints"][0]
    assert 条目["verified"] is False
    assert "超出" in 条目["reason"]
    assert 适配器.debugger.列出断点() == []


def test_setBreakpoints合法行返回已验证(新建适配器, tmp_path):
    路径 = 写程序(tmp_path)
    适配器 = 新建适配器()
    请求(适配器, "setBreakpoints", 1, source={"path": 路径}, breakpoints=[{"line": 2}])
    条目 = 响应(适配器.输出, "setBreakpoints", 1)["body"]["breakpoints"][0]
    assert 条目["verified"] is True
    assert "reason" not in 条目
    assert len(适配器.debugger.列出断点()) == 1
