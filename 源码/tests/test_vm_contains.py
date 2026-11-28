"""VM 成员运算符（在 / 不在）正确性回归测试。

此前字节码编译器未为「在」发射任何 opcode，导致 `x 在 容器` 直接把容器
留在栈顶（恒真），与 AST 解释器语义不一致。这里覆盖列表/文本/字典、反向
运算、条件与匹配守卫、JIT 路径和非法容器报错。
"""

import sys
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dao.bytecode.compiler import BytecodeCompiler
from dao.bytecode.disassembler import Disassembler
from dao.bytecode.opcodes import OpCode
from dao.errors import 类型错误
from dao.lexer import Lexer
from dao.parser import Parser
from dao.vm.core import VirtualMachine


def _compile(source: str):
    return BytecodeCompiler().compile(Parser(Lexer(source).tokenize()).parse())


def run_vm(source: str, *, jit: bool = False) -> str:
    vm = VirtualMachine()
    if jit:
        vm.enable_jit(threshold=2)
    buf = StringIO()
    with redirect_stdout(buf):
        vm.run(_compile(source))
    return buf.getvalue()


def test_compiler_emits_contains_opcodes():
    code = _compile("打印(3 在 [1, 2, 3])\n打印(4 不在 [1, 2, 3])")
    ops = [inst.opcode for inst in code.instructions]
    assert OpCode.CONTAINS in ops
    assert OpCode.NOT_CONTAINS in ops
    assert "CONTAINS" in Disassembler().disassemble(code)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("打印(3 在 [1, 2, 3])", "真\n"),
        ("打印(7 在 [1, 2, 3])", "假\n"),
        ("打印(7 不在 [1, 2, 3])", "真\n"),
        ("打印(2 不在 [1, 2, 3])", "假\n"),
        ('打印("道" 在 "道语言")', "真\n"),
        ('打印("Java" 在 "道语言")', "假\n"),
        ('打印("甲" 在 {"甲": 1, "乙": 2})', "真\n"),
        ('打印("丙" 在 {"甲": 1, "乙": 2})', "假\n"),
    ],
)
def test_membership_literals(source, expected):
    assert run_vm(source) == expected


def test_membership_in_condition_matches_ast_semantics():
    source = (
        "函数 检查(x)\n"
        "    如果 x 在 [3, 4, 5]\n"
        "        返回 真\n"
        "    返回 假\n"
        "打印(检查(7))\n"
        "打印(检查(4))\n"
    )
    assert run_vm(source) == "假\n真\n"


def test_membership_in_match_guard():
    source = (
        "函数 季节(月份)\n"
        "    匹配 月份\n"
        "        情况 _ 当 月份 在 [3, 4, 5]: 返回 \"春天\"\n"
        "        情况 _ 当 月份 在 [6, 7, 8]: 返回 \"夏天\"\n"
        "        情况 _: 返回 \"其它\"\n"
        "打印(季节(3))\n"
        "打印(季节(7))\n"
        "打印(季节(12))\n"
    )
    assert run_vm(source) == "春天\n夏天\n其它\n"


def test_membership_under_jit():
    source = (
        "函数 检查(x)\n"
        "    如果 x 在 [3, 4]\n"
        "        返回 真\n"
        "    返回 假\n"
        "打印(检查(3) + 检查(9) + 检查(4))\n"
    )
    assert run_vm(source, jit=True) == "2\n"


def test_invalid_container_raises_chinese_error():
    with pytest.raises(类型错误, match="不支持成员检查"):
        run_vm("打印(1 在 42)")
