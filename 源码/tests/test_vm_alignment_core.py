"""AST 解释器 / VM 字节码语义对齐的差分回归测试。

同一份道语言源码分别交给 AST 解释器（唯一语义基准）与
``BytecodeCompiler`` + ``VirtualMachine``，比较标准输出与异常
（异常类型名 + 去掉行列前缀后的关键消息）。

产品代码正由其他代理并行修改，未落地时对应用例会失败；
请保留失败断言，不要修改产品源码来让测试通过。
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


def _parse(source: str):
    return Parser(Lexer(source).tokenize()).parse()


def _ast_run(source: str):
    return Interpreter().execute(_parse(source))


def _vm_run(source: str):
    return VirtualMachine().run(BytecodeCompiler().compile(_parse(source)))


_位置前缀 = re.compile(r"\[(?:文件:[^\],]+,\s*)?行\s*\d+,\s*列\s*\d+\]\s*")
_调用栈 = re.compile(r"\n\n调用栈:.*", re.DOTALL)


def _规范异常(exc: BaseException) -> tuple[str, str]:
    """去掉行号/调用栈等格式差异，只保留异常类型与关键中文消息。"""
    msg = _位置前缀.sub("", str(exc))
    msg = _调用栈.sub("", msg).strip()
    first = msg.splitlines()[0].strip() if msg else ""
    return type(exc).__name__, first


def _结果(runner, source: str) -> tuple[str, tuple[str, str] | None]:
    """返回 (标准输出, 异常信息或 None)。"""
    buf = io.StringIO()
    err = None
    try:
        with redirect_stdout(buf):
            runner(source)
    except Exception as exc:  # noqa: BLE001 - 差分测试需捕获所有执行异常
        err = _规范异常(exc)
    return buf.getvalue(), err


def _断言一致(source: str, runner=_vm_run) -> tuple[str, tuple[str, str] | None]:
    """AST 与 VM（默认）必须一致；返回 AST 侧结果以便进一步断言基准值。"""
    ast_结果 = _结果(_ast_run, source)
    vm_结果 = _结果(runner, source)
    assert vm_结果 == ast_结果, (
        f"源码:\n{source}\n---\nAST: {ast_结果!r}\nVM : {vm_结果!r}"
    )
    return ast_结果


def _结果_执行(执行) -> tuple[str, tuple[str, str] | None]:
    """对已构造好的 AST 执行体捕获输出与异常。"""
    buf = io.StringIO()
    err = None
    try:
        with redirect_stdout(buf):
            执行()
    except Exception as exc:  # noqa: BLE001
        err = _规范异常(exc)
    return buf.getvalue(), err


def _调用展开程序():
    """构造 f(1, ...其余) 的 AST。

    解析器尚未支持函数调用位置参数中的 ``...``，因此这里直接构造节点。
    每次调用返回全新的 Program，避免 AST 执行时的宏展开污染另一模式。
    """
    prog = _parse("函数 f(a, b)\n    返回 a + b\n定义 其余 = [1, 2]\n")
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


def _断言消息一致(source: str) -> tuple[str, tuple[str, str] | None]:
    """只比较输出与关键消息，不比较异常类型。

    AST 解释器在函数调用处会把内部 ``名称错误`` 包装成 ``运行时错误``，
    与项目既有 ``test_dual_mode.py`` 的约定一致：此处仅要求消息一致。
    """
    ast_结果 = _结果(_ast_run, source)
    vm_结果 = _结果(_vm_run, source)
    assert vm_结果[0] == ast_结果[0]
    assert (vm_结果[1] is None) == (ast_结果[1] is None)
    if ast_结果[1] is not None:
        assert vm_结果[1][1] == ast_结果[1][1]
    return ast_结果


class Test默认参数:
    def test_默认参数基本差分(self):
        结果 = _断言一致("函数 加(a, b=2)\n    返回 a+b\n打印(加(1))")
        assert 结果 == ("3\n", None)

    def test_默认参数与关键字参数混合(self):
        结果 = _断言一致(
            "函数 f(a, b=2, c=3)\n    返回 a*100+b*10+c\n打印(f(1, c=7))"
        )
        assert 结果 == ("127\n", None)

    def test_默认参数被显式覆盖(self):
        结果 = _断言一致("函数 f(a, b=2)\n    返回 a+b\n打印(f(1, 9))")
        assert 结果 == ("10\n", None)


class Test变长参数:
    def test_变长参数收集为列表(self):
        结果 = _断言一致("函数 f(a, ...剩余)\n    返回 剩余\n打印(f(1, 2, 3))")
        assert 结果 == ("[2, 3]\n", None)

    def test_变长参数为空(self):
        结果 = _断言一致("函数 f(a, ...剩余)\n    返回 剩余\n打印(f(1))")
        assert 结果 == ("[]\n", None)


class Test关键字参数:
    def test_关键字参数差分(self):
        结果 = _断言一致("函数 f(a, b)\n    返回 a-b\n打印(f(1, b=3))")
        assert 结果 == ("-2\n", None)

    def test_关键字参数顺序重排(self):
        结果 = _断言一致(
            "函数 f(a, b, c)\n    返回 a*100+b*10+c\n打印(f(1, c=3, b=2))"
        )
        assert 结果 == ("123\n", None)


class Test解构赋值:
    def test_列表解构声明(self):
        结果 = _断言一致("定义 [甲, 乙] = [1, 2]\n打印(甲)\n打印(乙)")
        assert 结果 == ("1\n2\n", None)

    def test_列表解构重新赋值_交换(self):
        结果 = _断言一致("定义 a = 1\n定义 b = 2\n[a, b] = [b, a]\n打印(a)\n打印(b)")
        assert 结果 == ("2\n1\n", None)

    def test_解构剩余元素(self):
        结果 = _断言一致("定义 [头, ...尾] = [1, 2, 3]\n打印(头)\n打印(尾)")
        assert 结果 == ("1\n[2, 3]\n", None)

    def test_字典解构(self):
        结果 = _断言一致('定义 人 = {"姓名": "张三"}\n定义 {姓名} = 人\n打印(姓名)')
        assert 结果 == ("张三\n", None)


class Test成员赋值:
    def test_普通成员赋值(self):
        结果 = _断言一致(
            "类型 点\n    定义 x = 0\n定义 p = 点()\np.x = 9\n打印(p.x)"
        )
        assert 结果 == ("9\n", None)

    def test_setter赋值(self):
        src = (
            "类型 温度\n"
            "    初始化()\n"
            "        本对象._摄氏 = 0\n"
            "    设置 摄氏(值)\n"
            "        本对象._摄氏 = 值 * 2\n"
            "    获取 摄氏()\n"
            "        返回 本对象._摄氏\n"
            "定义 t = 温度()\n"
            "t.摄氏 = 5\n"
            "打印(t.摄氏)"
        )
        结果 = _断言一致(src)
        assert 结果 == ("10\n", None)

    def test_私有成员读取被拒绝(self):
        src = (
            "类型 动物\n"
            "    初始化(名字)\n"
            "        本对象.名字 = 名字\n"
            "        私有 本对象.年龄 = 0\n"
            '定义 小猫 = 动物("咪咪")\n'
            "打印(小猫.年龄)"
        )
        结果 = _断言一致(src)
        assert 结果[0] == ""
        assert 结果[1][0] == "运行时错误"
        assert "私有成员" in 结果[1][1]

    def test_私有成员写入被拒绝(self):
        src = (
            "类型 动物\n"
            "    初始化(名字)\n"
            "        本对象.名字 = 名字\n"
            "        私有 本对象.年龄 = 0\n"
            '定义 小猫 = 动物("咪咪")\n'
            "小猫.年龄 = 5"
        )
        结果 = _断言一致(src)
        assert 结果[0] == ""
        assert 结果[1][0] == "运行时错误"
        assert "私有成员" in 结果[1][1]


class Test下标赋值:
    def test_列表下标赋值(self):
        结果 = _断言一致("定义 a = [1, 2]\na[0] = 9\n打印(a)")
        assert 结果 == ("[9, 2]\n", None)

    def test_字典下标赋值(self):
        结果 = _断言一致('定义 d = {"a": 1}\nd["b"] = 2\n打印(d)')
        assert 结果 == ("{'a': 1, 'b': 2}\n", None)


class Test断言:
    def test_断言失败中断后续语句(self):
        结果 = _断言一致('断言 假, "错了"\n打印("到此")')
        assert 结果[0] == ""
        assert 结果[1] == ("断言失败", "错了")

    def test_断言成功继续执行(self):
        结果 = _断言一致('断言 真, "通过"\n打印("到此")')
        assert 结果 == ("到此\n", None)


class Test常量:
    def test_常量重写被拒绝(self):
        结果 = _断言一致("常量 X = 1\nX = 2\n打印(X)")
        assert 结果[0] == ""
        assert 结果[1] == ("运行时错误", "常量 'X' 不能被重新赋值")

    def test_常量跨赋值仍被拒绝(self):
        src = (
            "常量 X = 1\n"
            "定义 Y = 2\n"
            "Y = X + 1\n"
            "X = 99\n"
            "打印(X)\n"
            "打印(Y)"
        )
        结果 = _断言一致(src)
        assert 结果[0] == ""
        assert 结果[1] == ("运行时错误", "常量 'X' 不能被重新赋值")


class Test生成器:
    def test_产出序列(self):
        src = (
            "函数 g()\n"
            "    产出 1\n"
            "    产出 2\n"
            "遍历 x 在 g()\n"
            "    打印(x)"
        )
        结果 = _断言一致(src)
        assert 结果 == ("1\n2\n", None)

    def test_产出带计算(self):
        src = (
            "函数 平方们(n)\n"
            "    遍历 i 从 1 到 n\n"
            "        产出 i * i\n"
            "遍历 x 在 平方们(3)\n"
            "    打印(x)"
        )
        结果 = _断言一致(src)
        assert 结果 == ("1\n4\n9\n", None)


class Test异步函数:
    def test_异步函数等待(self):
        结果 = _断言一致("异步函数 f()\n    返回 1\n打印(等待 f())")
        assert 结果 == ("1\n", None)

    def test_等待普通值(self):
        结果 = _断言一致("打印(等待 42)")
        assert 结果 == ("42\n", None)


class Test文本乘小数:
    def test_文本乘小数取整(self):
        结果 = _断言一致('打印("啊" * 2.0)')
        assert 结果 == ("啊啊\n", None)

    def test_文本乘小数向下取整(self):
        结果 = _断言一致('打印("ab" * 2.9)')
        assert 结果 == ("abab\n", None)


class Test整除除零:
    def test_整除除零(self):
        结果 = _断言一致("打印(1 // 0)")
        assert 结果[0] == ""
        assert 结果[1] == ("运行时错误", "除零错误")

    def test_普通除法除零仍对齐(self):
        结果 = _断言一致("打印(1 / 0)")
        assert 结果[0] == ""
        assert 结果[1][0] == "运行时错误"
        assert "除零" in 结果[1][1]


class Test展开:
    def test_列表展开(self):
        结果 = _断言一致("定义 其余 = [2, 3]\n打印([1, ...其余])")
        assert 结果 == ("[1, 2, 3]\n", None)

    def test_多列表展开(self):
        结果 = _断言一致(
            "定义 甲 = [1, 2]\n定义 乙 = [3, 4]\n"
            "定义 合并 = [...甲, ...乙]\n打印(合并)"
        )
        assert 结果 == ("[1, 2, 3, 4]\n", None)

    def test_字典展开(self):
        结果 = _断言一致(
            '定义 原始 = {"a": 1}\n定义 新 = {...原始, "b": 2}\n打印(新)'
        )
        assert 结果 == ("{'a': 1, 'b': 2}\n", None)

    def test_嵌套展开(self):
        结果 = _断言一致(
            "定义 里 = [2, 3]\n定义 外 = [1, ...里, 4]\n"
            "定义 更外 = [0, ...外]\n打印(更外)"
        )
        assert 结果 == ("[0, 1, 2, 3, 4]\n", None)

    def test_集合展开语法在两模式一致(self):
        # AST 解释器本身不支持集合字面量中的展开语法，两模式应给出一致结果。
        结果 = _断言一致("定义 s = {1, 2}\n定义 t = {0, ...s}\n打印(长度(t))")
        assert 结果[0] == ""
        assert 结果[1] == ("语法错误", "无法解析的表达式: '...' (展开)")


class Test枚举注解:
    def test_枚举带注解(self):
        src = (
            "函数 标记(x)\n"
            "    打印(\"注解\")\n"
            "@标记\n"
            "枚举 色\n"
            "    红\n"
            "打印(色.红)"
        )
        结果 = _断言一致(src)
        assert 结果 == ("注解\n色.红\n", None)


class Test并行语句:
    def test_并行块输出一致(self):
        结果 = _断言一致('并行\n    打印("甲")\n    打印("乙")')
        assert 结果 == ("甲\n乙\n", None)


class Test匹配守卫强制绑定:
    def test_守卫强制绑定已存在变量(self):
        # y 在外层已定义为 9；带守卫的标识符模式必须强制绑定匹配值 1。
        src = (
            "定义 x = 1\n"
            "定义 y = 9\n"
            "匹配 x\n"
            "    情况 y 当 y > 0\n"
            "        打印(\"绑定\")\n"
            "    情况 _\n"
            "        打印(\"通配\")"
        )
        结果 = _断言一致(src)
        assert 结果 == ("绑定\n", None)

    def test_强制绑定后的值参与运算(self):
        src = (
            "定义 x = 5\n"
            "定义 y = 9\n"
            "匹配 x\n"
            "    情况 y 当 y > 0\n"
            "        打印(y)\n"
            "    情况 _\n"
            "        打印(0)"
        )
        结果 = _断言一致(src)
        assert 结果 == ("5\n", None)

    def test_守卫不满足时落到通配(self):
        src = (
            "定义 x = 1\n"
            "定义 y = 9\n"
            "匹配 x\n"
            "    情况 y 当 y > 10\n"
            "        打印(\"绑定\")\n"
            "    情况 _\n"
            "        打印(\"通配\")"
        )
        结果 = _断言一致(src)
        assert 结果 == ("通配\n", None)


class Test匹配与Try返回值:
    def test_匹配分支内返回(self):
        src = (
            "函数 f(x)\n"
            "    匹配 x\n"
            "        情况 1: 返回 10\n"
            "        情况 2: 返回 20\n"
            "    返回 0\n"
            "打印(f(2))"
        )
        结果 = _断言一致(src)
        assert 结果 == ("20\n", None)

    def test_try块内返回(self):
        src = (
            "函数 f()\n"
            "    尝试\n"
            "        返回 5\n"
            "    捕获 错误\n"
            "        返回 6\n"
            "打印(f())"
        )
        结果 = _断言一致(src)
        assert 结果 == ("5\n", None)

    def test_catch块内返回(self):
        src = (
            "函数 f()\n"
            "    尝试\n"
            '        抛出 "坏"\n'
            "    捕获 错误\n"
            "        返回 6\n"
            "打印(f())"
        )
        结果 = _断言一致(src)
        assert 结果 == ("6\n", None)


class Test运算符重载:
    def test_加法重载(self):
        src = "类型 点\n    运算符+(别的)\n        返回 99\n打印(点()+点())"
        结果 = _断言一致(src)
        assert 结果 == ("99\n", None)

    def test_乘法重载(self):
        src = (
            "类型 标量\n"
            "    初始化(v)\n"
            "        本对象.v = v\n"
            "    运算符*(别的)\n"
            "        返回 本对象.v * 别的.v\n"
            "打印(标量(6) * 标量(7))"
        )
        结果 = _断言一致(src)
        assert 结果 == ("42\n", None)


class Test未定义变量:
    def test_未定义变量错误类型(self):
        结果 = _断言一致("不存在的变量")
        assert 结果[0] == ""
        assert 结果[1] == ("名称错误", "变量 '不存在的变量' 未定义")

    def test_表达式中的未定义变量(self):
        结果 = _断言一致("定义 x = 1\nx + 不存在的变量")
        assert 结果[0] == ""
        assert 结果[1] == ("名称错误", "变量 '不存在的变量' 未定义")

    def test_函数内的未定义变量(self):
        # AST 会把函数内部的名称错误包装成运行时错误，故只比较关键消息。
        结果 = _断言消息一致("函数 f()\n    返回 不存在的变量\nf()")
        assert 结果[0] == ""
        assert 结果[1][1] == "变量 '不存在的变量' 未定义"


class Test未知运算符不污染栈:
    def test_不支持的二元运算可在两模式捕获(self):
        src = (
            "尝试\n"
            '  打印(1 - "a")\n'
            "捕获 错误\n"
            '  打印("已捕获")\n'
            '打印("继续")'
        )
        结果 = _断言一致(src)
        assert 结果 == ("已捕获\n继续\n", None)

    def test_字典与整数相加(self):
        结果 = _断言一致("打印({} + 1)")
        assert 结果[0] == ""
        assert 结果[1][0] == "TypeError"


class Test调用参数展开:
    def test_位置参数含展开时AST与VM一致(self):
        # 不硬编码期望值：AST 当前也把 SpreadExpr 视为未知表达式，
        # 若后续 AST 增加支持，只要 VM 经 DELEGATE_EXPR 委托后就仍应一致。
        ast_结果 = _结果_执行(lambda: Interpreter().execute(_调用展开程序()))
        vm_结果 = _结果_执行(
            lambda: VirtualMachine().run(
                BytecodeCompiler().compile(_调用展开程序())
            )
        )
        assert vm_结果 == ast_结果, f"AST: {ast_结果!r}\nVM : {vm_结果!r}"


class Test解释器内置函数与静态方法:
    def test_函数式内置在纯VM程序可用(self):
        src = (
            "定义 数列 = [1, 2, 3]\n"
            "打印(映射(数列, 函数(x) => x * 2))\n"
            "打印(折叠(数列, 0, 函数(a, b) => a + b))"
        )
        结果 = _断言一致(src)
        assert 结果 == ("[2, 4, 6]\n6\n", None)

    def test_类型对象静态方法与AST一致(self):
        src = (
            "类型 工具\n"
            "    静态 函数 平方(x)\n"
            "        返回 x * x\n"
            "打印(工具.平方(3))"
        )
        结果 = _断言一致(src)
        assert 结果 == ("9\n", None)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
