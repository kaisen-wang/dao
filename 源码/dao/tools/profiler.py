"""道语言性能分析器（profiler）
==============================

对 ``.道`` 程序做函数级计时分析：统计每个函数的调用次数、总耗时与平均耗时，
并按总耗时降序给出热点 Top-N。支持两种执行模式：

* ``interpreter``：树遍历解释器，插桩 ``Interpreter._call_dao_function``；
* ``vm``：字节码虚拟机，插桩 ``VirtualMachine._execute_frame``，按
  ``CodeObject.name`` 归属到具体函数（``<module>`` 顶层帧不计入函数统计）。

耗时使用 :func:`time.perf_counter` 测量，为包含内层调用的“累计耗时”，
与热点分析的直觉一致；单位均为秒。

命令行用法（在 ``源码`` 目录下运行）::

    python -m dao.tools.profiler 文件.道
    python -m dao.tools.profiler 文件.道 --mode vm --top 5

退出码：0 表示剖析成功，2 表示文件/参数/解析/运行错误。
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from ..bytecode.compiler import BytecodeCompiler
from ..interpreter import Interpreter
from ..lexer import Lexer
from ..parser import Parser
from ..vm import VirtualMachine

_MODES = ("interpreter", "vm")
_MODULE_FRAME = "<module>"


@dataclass
class FunctionStat:
    """单个函数的计时汇总。"""

    name: str
    calls: int = 0
    total_time: float = 0.0

    @property
    def average_time(self) -> float:
        """平均每次调用耗时（秒）。"""
        return self.total_time / self.calls if self.calls else 0.0

    def to_dict(self) -> dict:
        """可序列化的统计表示。"""
        return {
            "name": self.name,
            "calls": self.calls,
            "total_time": round(self.total_time, 9),
            "average_time": round(self.average_time, 9),
        }


@dataclass
class ProfileReport:
    """一次剖析的完整结果。"""

    mode: str
    filename: str
    elapsed: float = 0.0
    function_stats: dict[str, FunctionStat] = field(default_factory=dict)

    def top(self, n: int = 10) -> list[FunctionStat]:
        """按总耗时降序返回前 ``n`` 个函数（同耗时按调用次数、名称稳定排序）。"""
        ordered = sorted(
            self.function_stats.values(),
            key=lambda stat: (-stat.total_time, -stat.calls, stat.name),
        )
        return ordered[:max(0, n)]

    def to_dict(self, top_n: int = 10) -> dict:
        """可序列化的报告表示。"""
        return {
            "mode": self.mode,
            "filename": self.filename,
            "elapsed": round(self.elapsed, 9),
            "functions": [stat.to_dict() for stat in self.top(top_n)],
        }

    def render(self, top_n: int = 10) -> str:
        """渲染中文文本报告。"""
        stats = self.top(top_n)
        lines = [
            "道语言性能分析报告",
            "==================",
            f"文件: {self.filename}",
            f"模式: {self.mode}",
            f"总耗时: {self.elapsed:.6f} 秒",
            f"采样函数: {len(self.function_stats)} 个",
            "",
            f"函数级统计（按总耗时降序，前 {top_n} 项）:",
            "序号 | 函数名 | 调用次数 | 总耗时(秒) | 平均耗时(秒)",
        ]
        if not stats:
            lines.append("（本次运行未采样到用户函数）")
        else:
            for index, stat in enumerate(stats, 1):
                lines.append(
                    f"{index} | {stat.name} | {stat.calls} | "
                    f"{stat.total_time:.6f} | {stat.average_time:.6f}"
                )

        lines += ["", f"热点 Top {top_n}:"]
        if not stats:
            lines.append("（无热点）")
        else:
            for index, stat in enumerate(stats, 1):
                lines.append(
                    f"{index}. {stat.name} —— 调用 {stat.calls} 次，"
                    f"总耗时 {stat.total_time:.6f} 秒"
                )
        return "\n".join(lines)


class _Recorder:
    """线程内累积函数计时（道语言当前为单线程执行模型）。"""

    def __init__(self) -> None:
        self._stats: dict[str, FunctionStat] = {}

    def record(self, name: str, duration: float) -> None:
        stat = self._stats.setdefault(name, FunctionStat(name=name))
        stat.calls += 1
        stat.total_time += duration

    def snapshot(self) -> dict[str, FunctionStat]:
        return {name: FunctionStat(stat.name, stat.calls, stat.total_time)
                for name, stat in self._stats.items()}


def profile_source(
    source: str, filename: str = "<输入>", mode: str = "interpreter"
) -> ProfileReport:
    """剖析一段道语言源码，返回函数级性能报告。"""
    if mode not in _MODES:
        raise ValueError(f"未知模式“{mode}”，可用模式：{'、'.join(_MODES)}")

    tokens = Lexer(source, filename).tokenize()
    program = Parser(tokens, source).parse()
    recorder = _Recorder()

    started = time.perf_counter()
    if mode == "interpreter":
        interpreter = Interpreter()
        original_call = interpreter._call_dao_function

        def timed_call(func, args, kwargs, call_expr):
            call_started = time.perf_counter()
            try:
                return original_call(func, args, kwargs, call_expr)
            finally:
                name = getattr(func, "name", "<匿名函数>") or "<匿名函数>"
                recorder.record(name, time.perf_counter() - call_started)

        interpreter._call_dao_function = timed_call
        interpreter.execute(program, source=source)
    else:
        code = BytecodeCompiler().compile(program)
        vm = VirtualMachine()
        original_frame = vm._execute_frame

        def timed_frame(frame):
            name = getattr(getattr(frame, "code", None), "name", "") or "<未知函数>"
            if name == _MODULE_FRAME:
                return original_frame(frame)
            frame_started = time.perf_counter()
            try:
                return original_frame(frame)
            finally:
                recorder.record(name, time.perf_counter() - frame_started)

        vm._execute_frame = timed_frame
        vm.run(code)

    return ProfileReport(
        mode=mode,
        filename=filename,
        elapsed=time.perf_counter() - started,
        function_stats=recorder.snapshot(),
    )


def profile_file(path: str | Path, mode: str = "interpreter") -> ProfileReport:
    """剖析一个 ``.道`` 文件。"""
    file_path = Path(path)
    return profile_source(
        file_path.read_text(encoding="utf-8"), filename=str(file_path), mode=mode
    )


def main(argv: list[str] | None = None) -> int:
    """命令行入口。"""
    parser = argparse.ArgumentParser(
        prog="python -m dao.tools.profiler",
        description="道语言性能分析器（函数级调用次数、总耗时、平均耗时与热点 Top-N）",
    )
    parser.add_argument("file", help="待剖析的 .道 文件")
    parser.add_argument(
        "--mode", choices=_MODES, default="interpreter", help="执行模式（默认 interpreter）"
    )
    parser.add_argument("--top", type=int, default=10, help="热点榜显示条数（默认 10）")
    args = parser.parse_args(argv)

    if args.top < 0:
        print("错误：--top 不能为负数", file=sys.stderr)
        return 2

    try:
        report = profile_file(args.file, mode=args.mode)
    except FileNotFoundError:
        print(f"错误：文件不存在：{args.file}", file=sys.stderr)
        return 2
    except Exception as error:
        print(f"错误：无法剖析“{args.file}”：{error}", file=sys.stderr)
        return 2

    sys.stdout.write(report.render(args.top) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
