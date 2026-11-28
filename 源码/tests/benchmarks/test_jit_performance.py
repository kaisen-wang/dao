"""JIT 性能回归护栏：小规模进程内基准。

只断言 JIT 不慢于解释执行（留出充足余量避免 CI 抖动导致 flaky），
大规模性能验收以独立评估报告和外部基准脚本为准。
"""

import os
import statistics
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dao.bytecode.compiler import BytecodeCompiler
from dao.lexer import Lexer
from dao.parser import Parser
from dao.vm.core import VirtualMachine

_FIB_SOURCE = (
    "函数 fib(n)\n"
    "    如果 n <= 1\n"
    "        返回 n\n"
    "    返回 fib(n - 1) + fib(n - 2)\n"
    "fib(18)"
)
_LOOP_SOURCE = (
    "定义 总和 = 0\n"
    "遍历 i 从 0 到 19999\n"
    "    设 总和 = 总和 + i\n"
    "总和"
)


def _compile(source):
    return BytecodeCompiler().compile(Parser(Lexer(source).tokenize()).parse())


def _measure(code, jit, trials=3):
    timings = []
    result = None
    for _ in range(trials):
        vm = VirtualMachine()
        if jit:
            vm.enable_jit(threshold=3)
        start = time.perf_counter()
        result = vm.run(code)
        timings.append(time.perf_counter() - start)
    return statistics.median(timings), result


def test_jit_not_slower_than_vm_on_recursion():
    code = _compile(_FIB_SOURCE)
    vm_time, vm_result = _measure(code, jit=False)
    jit_time, jit_result = _measure(code, jit=True)
    assert jit_result == vm_result == 2584
    assert jit_time <= vm_time * 1.5


def test_jit_not_slower_than_vm_on_loop():
    code = _compile(_LOOP_SOURCE)
    vm_time, vm_result = _measure(code, jit=False)
    jit_time, jit_result = _measure(code, jit=True)
    assert jit_result == vm_result == 199990000
    assert jit_time <= vm_time * 1.5
