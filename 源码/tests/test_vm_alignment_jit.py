"""VM+JIT 与 AST 解释器的语义对齐差分测试。

对代表性源码开启 ``enable_jit(threshold=1)`` 强制走 JIT 编译路径，
验证其与 AST 基准在标准输出与异常上一致。
"""

import io
import os
import re
import sys
from contextlib import redirect_stdout

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.ast_nodes import (
    ExpressionStmt,
    FunctionCall,
    Identifier,
    NumberLiteral,
    SpreadExpr,
)
from dao.bytecode.compiler import BytecodeCompiler
from dao.interpreter.core import Interpreter
from dao.lexer import Lexer
from dao.parser import Parser
from dao.vm.core import VirtualMachine

_位置前缀 = re.compile(r"\[(?:文件:[^\],]+,\s*)?行\s*\d+,\s*列\s*\d+\]\s*")
_调用栈 = re.compile(r"\n\n调用栈:.*", re.DOTALL)


def _结果(runner, source: str) -> tuple[str, tuple[str, str] | None]:
    buf = io.StringIO()
    err = None
    try:
        with redirect_stdout(buf):
            runner(source)
    except Exception as exc:  # noqa: BLE001
        msg = _位置前缀.sub("", str(exc))
        msg = _调用栈.sub("", msg).strip()
        err = (type(exc).__name__, msg.splitlines()[0].strip() if msg else "")
    return buf.getvalue(), err


def _ast_run(source: str):
    return Interpreter().execute(Parser(Lexer(source).tokenize()).parse())


def _jit_run(source: str):
    vm = VirtualMachine()
    vm.enable_jit(threshold=1)
    code = BytecodeCompiler().compile(Parser(Lexer(source).tokenize()).parse())
    return vm.run(code)


# 至少 4 个代表性源码：覆盖委托语句、常量、展开、二元运算、异常
代表性源码 = {
    "默认参数与关键字": (
        "函数 f(a, b=2, c=3)\n"
        "    返回 a*100+b*10+c\n"
        "打印(f(1, c=7))"
    ),
    "变长参数": "函数 f(a, ...剩余)\n    返回 剩余\n打印(f(1, 2, 3))",
    "生成器": (
        "函数 g()\n"
        "    产出 1\n"
        "    产出 2\n"
        "遍历 x 在 g()\n"
        "    打印(x)"
    ),
    "异步等待": "异步函数 f()\n    返回 42\n打印(等待 f())",
    "常量重写": "常量 X = 1\nX = 2\n打印(X)",
    "断言失败": '断言 假, "错了"\n打印("到此")',
    "列表与字典展开": (
        "定义 甲 = [1, 2]\n"
        '定义 原始 = {"a": 1}\n'
        "定义 合并 = [...甲, 3]\n"
        '定义 新 = {...原始, "b": 2}\n'
        "打印(合并)\n"
        "打印(新)"
    ),
    "文本乘小数": '打印("ab" * 2.9)',
    "整除除零": "打印(1 // 0)",
    "枚举注解": (
        "函数 标记(x)\n"
        '    打印("注解")\n'
        "@标记\n"
        "枚举 色\n"
        "    红\n"
        "打印(色.红)"
    ),
    "并行语句": '并行\n    打印("甲")\n    打印("乙")',
    "运算符重载": "类型 点\n    运算符+(别的)\n        返回 99\n打印(点()+点())",
}


class TestVM加JIT对齐:
    @pytest.mark.parametrize("名称", list(代表性源码))
    def test_jit与ast一致(self, 名称):
        源码 = 代表性源码[名称]
        ast_结果 = _结果(_ast_run, 源码)
        jit_结果 = _结果(_jit_run, 源码)
        assert jit_结果 == ast_结果, (
            f"[{名称}] 源码:\n{源码}\n---\nAST: {ast_结果!r}\nJIT: {jit_结果!r}"
        )

    def test_调用位置参数展开与ast一致(self):
        # 解析器不支持 f(1, ...其余) 语法，直接构造 AST。
        def 程序():
            prog = Parser(Lexer("函数 f(a, b)\n    返回 a + b\n定义 其余 = [1, 2]\n").tokenize()).parse()
            调用 = FunctionCall(
                callee=Identifier(name="f"),
                arguments=[NumberLiteral(value=1), SpreadExpr(expression=Identifier(name="其余"))],
                line=4,
                column=1,
            )
            prog.statements.append(
                ExpressionStmt(
                    expression=FunctionCall(
                        callee=Identifier(name="打印"), arguments=[调用], line=4, column=1
                    ),
                    line=4,
                    column=1,
                )
            )
            return prog

        def 执行(模式):
            buf = io.StringIO()
            err = None
            try:
                with redirect_stdout(buf):
                    if 模式 == "ast":
                        Interpreter().execute(程序())
                    else:
                        vm = VirtualMachine()
                        vm.enable_jit(threshold=1)
                        vm.run(BytecodeCompiler().compile(程序()))
            except Exception as exc:  # noqa: BLE001
                err = (type(exc).__name__, str(exc).splitlines()[0])
            return buf.getvalue(), err

        ast_结果 = 执行("ast")
        jit_结果 = 执行("jit")
        assert jit_结果 == ast_结果, f"AST: {ast_结果!r}\nJIT: {jit_结果!r}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
