"""
道语言调试适配器（Debug Adapter Protocol）
==========================================

以 stdio 上的 JSON 帧实现 DAP 最小可用子集，让 VS Code 等 IDE 能够调试 .道 程序。
底层复用 dao.debug.debugger 的状态机（断点、单步、变量查看），不引入第三方包。

协议帧格式：:

    Content-Length: <字节数>\\r\\n
    \\r\\n
    {"seq": 1, "type": "request", "command": "initialize", ...}

命令行入口：:

    python -m dao.debug.dap

支持的请求见 SUPPORTED_COMMANDS。
"""

from __future__ import annotations

import json
import os
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

from ..lexer import Lexer
from ..parser import Parser
from .debugger import DebugExecutor, Debugger, 暂停事件, 调试指令

SUPPORTED_COMMANDS = (
    "initialize",
    "launch",
    "setBreakpoints",
    "configurationDone",
    "stackTrace",
    "scopes",
    "variables",
    "continue",
    "next",
    "stepIn",
    "stepOut",
    "evaluate",
    "threads",
    "disconnect",
    # 客户端常发的无副作用请求，给空响应以保持兼容
    "setExceptionBreakpoints",
)


class DAP帧错误(ValueError):
    """DAP 帧格式错误。"""


def 编码消息(消息: dict) -> bytes:
    """把一个 DAP 消息编码为 Content-Length 帧。"""
    正文 = json.dumps(消息, ensure_ascii=False).encode("utf-8")
    头 = f"Content-Length: {len(正文)}\r\n\r\n".encode("ascii")
    return 头 + 正文


def 解码消息(数据: bytes) -> tuple[list[dict], bytes]:
    """
    从字节缓冲中解析出所有完整的 DAP 帧。

    返回 ``(消息列表, 尚未解析的剩余字节)``。头部大小写不敏感，
    允许附带 Content-Type 等额外头；JSON 正文必须是 UTF-8。
    """
    消息列表: list[dict] = []
    余量 = 数据
    while True:
        分隔位置 = 余量.find(b"\r\n\r\n")
        if 分隔位置 < 0:
            break
        头段 = 余量[:分隔位置].decode("ascii", errors="replace")
        长度 = None
        for 行 in 头段.split("\r\n"):
            名称, _, 值 = 行.partition(":")
            if 名称.strip().lower() == "content-length":
                try:
                    长度 = int(值.strip())
                except ValueError as 异常:
                    raise DAP帧错误(f"非法 Content-Length: {值!r}") from 异常
                break
        if 长度 is None:
            raise DAP帧错误("DAP 帧缺少 Content-Length 头")
        if 长度 < 0:
            raise DAP帧错误("Content-Length 不能为负数")
        正文起点 = 分隔位置 + 4
        正文终点 = 正文起点 + 长度
        if len(余量) < 正文终点:
            break  # 正文尚未收齐
        正文 = 余量[正文起点:正文终点]
        try:
            消息列表.append(json.loads(正文.decode("utf-8")))
        except (UnicodeDecodeError, json.JSONDecodeError) as 异常:
            raise DAP帧错误(f"DAP 正文不是合法 UTF-8 JSON: {异常}") from 异常
        余量 = 余量[正文终点:]
    return 消息列表, 余量


class DAP消息流:
    """基于二进制流的 DAP 帧读写器。"""

    def __init__(self, reader: BinaryIO, writer: BinaryIO):
        self.reader = reader
        self.writer = writer
        self._缓冲 = b""
        self._队列: list[dict] = []
        self._发送锁 = threading.Lock()

    def 读取消息(self) -> dict | None:
        """阻塞读取一条消息；流结束时返回 None。"""
        while not self._队列:
            分块 = self.reader.read(4096)
            if not 分块:
                return None
            self._缓冲 += 分块
            消息列表, self._缓冲 = 解码消息(self._缓冲)
            self._队列.extend(消息列表)
        return self._队列.pop(0)

    def 发送消息(self, 消息: dict) -> None:
        帧 = 编码消息(消息)
        with self._发送锁:
            self.writer.write(帧)
            self.writer.flush()


@dataclass
class _栈帧:
    编号: int
    名称: str
    文件: str
    行号: int
    列号: int
    环境: Any


class _程序输出桥:
    """把被调试程序的 stdout 转发为 DAP output 事件，避免污染协议帧。"""

    def __init__(self, 适配器: DAP适配器):
        self.适配器 = 适配器

    def write(self, 文本: str) -> int:
        if 文本 and self.适配器.已连接:
            self.适配器.发送事件("output", {"category": "stdout", "output": 文本})
        return len(文本)

    def flush(self) -> None:
        return None

    def isatty(self) -> bool:
        return False

    def writable(self) -> bool:
        return True


class DAP适配器:
    """stdio DAP 适配器，可嵌入测试（直接传入 BinaryIO）。"""

    线程编号 = 1

    def __init__(self, reader: BinaryIO | None = None, writer: BinaryIO | None = None):
        self.流 = DAP消息流(
            reader if reader is not None else sys.stdin.buffer,
            writer if writer is not None else sys.stdout.buffer,
        )
        self.debugger = Debugger()
        self.执行器: DebugExecutor | None = None
        self.源程序 = ""
        self.文件路径 = ""
        self.已启动 = False
        self.配置完成 = False
        self.已连接 = True
        self.停止于入口 = False
        self.首语句 = True
        self.停止原因 = ""
        self.暂停事件: 暂停事件 | None = None
        self.恢复事件 = threading.Event()
        self.恢复事件.set()
        self.执行线程: threading.Thread | None = None
        self.命令 = "continue"
        self.步深度: int | None = None
        self.帧列表: list[_栈帧] = []
        self.变量表: dict[int, Any] = {}
        self.下一个变量引用 = 1
        self.下一个序号 = 1
        self.异常退出 = False
        self._状态锁 = threading.RLock()

    # ---------------- 消息收发 ----------------
    def _取序号(self) -> int:
        序号 = self.下一个序号
        self.下一个序号 += 1
        return 序号

    def 发送事件(self, 事件名: str, 正文: dict | None = None) -> None:
        self.流.发送消息(
            {"seq": self._取序号(), "type": "event", "event": 事件名, "body": 正文 or {}}
        )

    def 发送响应(
        self,
        请求: dict,
        正文: dict | None = None,
        成功: bool = True,
        消息: str | None = None,
    ) -> None:
        响应: dict[str, Any] = {
            "seq": self._取序号(),
            "type": "response",
            "request_seq": 请求.get("seq", 0),
            "success": 成功,
            "command": 请求.get("command", ""),
        }
        if 消息:
            响应["message"] = 消息
        if 正文 is not None:
            响应["body"] = 正文
        self.流.发送消息(响应)

    # ---------------- 分派与主循环 ----------------
    def 处理消息(self, 消息: dict) -> None:
        if 消息.get("type") != "request":
            return
        命令 = 消息.get("command", "")
        处理器 = getattr(self, f"_处理{命令}", None)
        if 处理器 is None:
            self.发送响应(消息, 成功=False, 消息=f"不支持的请求: {命令}")
            return
        处理器(消息)

    def run(self) -> None:
        """持续读取并处理请求，直到收到 disconnect 或输入流结束。"""
        while self.已连接:
            消息 = self.流.读取消息()
            if 消息 is None:
                break
            self.处理消息(消息)

    # ---------------- 具体请求 ----------------
    def _处理initialize(self, 请求: dict) -> None:
        self.发送响应(
            请求,
            {
                "supportsConfigurationDoneRequest": True,
                "supportsEvaluateForHovers": True,
                "supportsFunctionBreakpoints": False,
                "supportsConditionalBreakpoints": False,
                "supportsStepBack": False,
                "supportsSetVariable": False,
                "supportsRestartRequest": False,
                "exceptionBreakpointFilters": [],
            },
        )
        self.发送事件("initialized")

    def _处理setExceptionBreakpoints(self, 请求: dict) -> None:
        self.发送响应(请求, {"breakpoints": []})

    def _处理setBreakpoints(self, 请求: dict) -> None:
        参数 = 请求.get("arguments") or {}
        源 = 参数.get("source") or {}
        路径 = self._规范化路径(源.get("path", ""))
        断点列表 = 参数.get("breakpoints")
        if 断点列表 is None:  # 兼容旧版 args.lines
            断点列表 = [{"line": 行} for 行 in 参数.get("lines", [])]

        for 旧断点 in self.debugger.列出断点():
            if 旧断点.文件 == 路径:
                self.debugger.删除断点(路径, 旧断点.行号)

        结果 = []
        for 序号, 断点参数 in enumerate(断点列表, start=1):
            行号 = 断点参数.get("line", 0)
            if not isinstance(行号, int) or 行号 < 1:
                continue
            self.debugger.设置断点(路径, 行号)
            结果.append({"id": 序号, "verified": True, "line": 行号})
        self.发送响应(请求, {"breakpoints": 结果})

    def _处理launch(self, 请求: dict) -> None:
        参数 = 请求.get("arguments") or {}
        程序 = 参数.get("program")
        if not 程序:
            self.发送响应(请求, 成功=False, 消息="launch 缺少 arguments.program")
            return
        try:
            self.源程序 = Path(程序).read_text(encoding="utf-8")
        except OSError as 异常:
            self.发送响应(请求, 成功=False, 消息=f"无法读取程序 {程序}: {异常}")
            return
        self.文件路径 = self._规范化路径(程序)
        self.停止于入口 = bool(参数.get("stopOnEntry", False))
        self.debugger.启用 = not bool(参数.get("noDebug", False))
        self.发送响应(请求)
        if self.配置完成:
            self._启动()

    def _处理configurationDone(self, 请求: dict) -> None:
        self.配置完成 = True
        self.发送响应(请求)
        if self.源程序:
            self._启动()

    def _处理threads(self, 请求: dict) -> None:
        self.发送响应(
            请求, {"threads": [{"id": self.线程编号, "name": "主线程"}]}
        )

    def _处理stackTrace(self, 请求: dict) -> None:
        帧数据 = []
        for 帧 in self.帧列表:
            帧数据.append(
                {
                    "id": 帧.编号,
                    "name": 帧.名称,
                    "source": {
                        "name": os.path.basename(帧.文件),
                        "path": 帧.文件,
                    }
                    if 帧.文件
                    else None,
                    "line": max(1, 帧.行号),
                    "column": max(1, 帧.列号),
                    "presentationHint": "normal",
                }
            )
        self.发送响应(
            请求, {"stackFrames": 帧数据, "totalFrames": len(帧数据)}
        )

    def _处理scopes(self, 请求: dict) -> None:
        self.发送响应(
            请求,
            {
                "scopes": [
                    {
                        "name": "局部变量",
                        "variablesReference": 1,
                        "namedVariables": len(self.变量表.get(1, {})),
                        "indexedVariables": 0,
                        "expensive": False,
                    }
                ]
            },
        )

    def _处理variables(self, 请求: dict) -> None:
        引用 = (请求.get("arguments") or {}).get("variablesReference", 0)
        目标 = self.变量表.get(引用)
        条目: list[tuple[str, Any]] = []
        if isinstance(目标, dict):
            # 全局环境预置了大量内置函数，局部变量视图只显示用户可见的变量。
            from ..builtins import get_builtins, get_interpreter_builtins

            内置名称 = set(get_builtins()) | set(get_interpreter_builtins())
            条目 = [
                (str(键), 值)
                for 键, 值 in 目标.items()
                if str(键) not in 内置名称
            ]
        elif isinstance(目标, (list, tuple)):
            条目 = [(str(序号), 值) for 序号, 值 in enumerate(目标)]
        变量 = []
        for 名称, 值 in 条目:
            变量.append(
                {
                    "name": 名称,
                    "value": _格式化值(值),
                    "type": type(值).__name__,
                    "variablesReference": self._容器引用(值),
                }
            )
        self.发送响应(请求, {"variables": 变量})

    def _处理evaluate(self, 请求: dict) -> None:
        参数 = 请求.get("arguments") or {}
        表达式 = 参数.get("expression", "")
        try:
            词法 = Lexer(表达式)
            语法 = Parser(词法.tokenize(), 表达式)
            表达式节点 = 语法.parse_expression()
            环境 = (
                self.暂停事件.环境
                if self.暂停事件 is not None
                else (self.执行器.global_env if self.执行器 else None)
            )
            if 环境 is None or self.执行器 is None:
                raise RuntimeError("程序尚未启动，无法求值")
            值 = self.执行器.eval_expression(表达式节点, 环境)
            self.发送响应(
                请求,
                {
                    "result": _格式化值(值),
                    "type": type(值).__name__,
                    "variablesReference": self._容器引用(值),
                },
            )
        except Exception as 异常:
            self.发送响应(请求, 成功=False, 消息=f"求值失败: {异常}")

    def _处理continue(self, 请求: dict) -> None:
        self.发送响应(请求, {"allThreadsContinued": True})
        self.发送事件(
            "continued", {"threadId": self.线程编号, "allThreadsContinued": True}
        )
        self._恢复("continue")

    def _处理next(self, 请求: dict) -> None:
        self.发送响应(请求)
        self._恢复("next")

    def _处理stepIn(self, 请求: dict) -> None:
        self.发送响应(请求)
        self._恢复("stepIn")

    def _处理stepOut(self, 请求: dict) -> None:
        self.发送响应(请求)
        self._恢复("stepOut")

    def _处理disconnect(self, 请求: dict) -> None:
        self.发送响应(请求)
        self.已连接 = False
        self.恢复事件.set()

    # ---------------- 执行与暂停 ----------------
    def _规范化路径(self, 路径: str) -> str:
        return os.path.abspath(路径) if 路径 else ""

    def _启动(self) -> None:
        if self.执行线程 is not None:
            return
        try:
            语法树 = Parser(Lexer(self.源程序, self.文件路径).tokenize(), self.源程序).parse()
        except Exception as 异常:
            self.发送事件(
                "output",
                {"category": "stderr", "output": f"语法解析失败: {异常}\n"},
            )
            self.发送事件("terminated")
            self.发送事件("exited", {"exitCode": 1})
            return
        self.执行器 = DebugExecutor(self.debugger, 文件名=self.文件路径)
        self.debugger.暂停回调 = self._暂停回调
        self.debugger.复位()
        self.debugger.单步 = self.debugger.启用
        self.执行线程 = threading.Thread(
            target=self._执行, args=(语法树,), daemon=True, name="dao-dap-debuggee"
        )
        self.执行线程.start()

    def _执行(self, 语法树: Any) -> None:
        原输出 = sys.stdout
        sys.stdout = _程序输出桥(self)  # type: ignore[assignment]
        try:
            self.执行器.execute(语法树, source=self.源程序)
        except Exception as 异常:
            self.异常退出 = True
            if self.已连接:
                self.发送事件(
                    "output",
                    {"category": "stderr", "output": f"程序异常: {异常}\n"},
                )
        finally:
            sys.stdout = 原输出
            if self.已连接:
                self.发送事件("terminated")
                self.发送事件("exited", {"exitCode": 1 if self.异常退出 else 0})

    def _暂停回调(self, 事件: 暂停事件):
        """由 DebugExecutor 在每条语句前调用；决定是否在此处停住并等待客户端。"""
        if not self.已连接:
            return 调试指令.继续

        命中断点 = any(
            断点.启用
            and 断点.行号 == 事件.行号
            and 断点.文件 in ("", 事件.文件)
            for 断点 in self.debugger.列出断点()
        )
        深度 = len(事件.调用栈)
        入口暂停 = self.停止于入口 and self.首语句

        if self.命令 == "continue":
            应停 = 命中断点 or 入口暂停
        elif self.命令 == "next":
            应停 = 命中断点 or 入口暂停 or (
                self.步深度 is not None and 深度 <= self.步深度
            )
        elif self.命令 == "stepIn":
            应停 = True
        elif self.命令 == "stepOut":
            应停 = 命中断点 or (
                self.步深度 is not None and 深度 < self.步深度
            )
        else:
            应停 = 命中断点

        self.首语句 = False
        if not 应停:
            return 调试指令.继续

        原因 = (
            "breakpoint"
            if 命中断点
            else ("entry" if 入口暂停 else "step")
        )
        with self._状态锁:
            self.暂停事件 = 事件
            self.停止原因 = 原因
            self._刷新帧与变量(事件)
        self.恢复事件.clear()
        self.发送事件(
            "stopped",
            {
                "reason": 原因,
                "threadId": self.线程编号,
                "text": None,
                "description": f"在第 {事件.行号} 行暂停（{原因}）",
            },
        )
        self.恢复事件.wait()
        return 调试指令.继续

    def _恢复(self, 命令: str) -> None:
        with self._状态锁:
            self.命令 = 命令
            if 命令 in ("next", "stepIn", "stepOut"):
                self.步深度 = (
                    len(self.暂停事件.调用栈) if self.暂停事件 is not None else 1
                )
            else:
                self.步深度 = None
            self.暂停事件 = None
            self.帧列表 = []
        self.恢复事件.set()

    def _刷新帧与变量(self, 事件: 暂停事件) -> None:
        self.帧列表 = [
            _栈帧(
                编号=1001,
                名称=(事件.调用栈[-1].get("function") if 事件.调用栈 else None)
                or "<顶层>",
                文件=事件.文件,
                行号=事件.行号,
                列号=事件.列号,
                环境=事件.环境,
            )
        ]
        for 序号, 外层 in enumerate(reversed(事件.调用栈[:-1]), start=1002):
            self.帧列表.append(
                _栈帧(
                    编号=序号,
                    名称=外层.get("function") or "<函数>",
                    文件=外层.get("file") or 事件.文件,
                    行号=外层.get("line") or 事件.行号,
                    列号=1,
                    环境=事件.环境,
                )
            )
        self.变量表 = {1: 事件.环境.values}
        self.下一个变量引用 = 2

    def _容器引用(self, 值: Any) -> int:
        if not isinstance(值, (dict, list, tuple)) or not 值:
            return 0
        引用 = self.下一个变量引用
        self.下一个变量引用 += 1
        self.变量表[引用] = 值
        return 引用


def _格式化值(值: Any) -> str:
    if 值 is None:
        return "空"
    if isinstance(值, bool):
        return "真" if 值 else "假"
    if isinstance(值, str):
        return repr(值)
    return str(值)


def main(argv: list[str] | None = None) -> int:
    """``python -m dao.debug.dap`` 的命令行入口。"""
    DAP适配器().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
