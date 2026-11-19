"""宏返回列表整体传递（不再被拆包）的回归测试
==============================================

根因：eval_macro_call() 末尾的循环对任意 list 强制拆包（单元素取 [0]、
多元素取 [-1]），导致宏返回的 [1,2,3] 被压成 3。

修复：循环只处理带 __type__ 的 dict（DataToAST 回转换），普通 list 作为
整体返回。字符串成员/标量返回值不受影响。
"""

import io
import os
import sys
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dao.interpreter import Interpreter
from dao.lexer import Lexer
from dao.macros.registry import MacroRegistry
from dao.parser import Parser


def run(source: str) -> str:
    MacroRegistry().clear()
    interpreter = Interpreter()
    ast = Parser(Lexer(source).tokenize(), source).parse()
    f = io.StringIO()
    with redirect_stdout(f):
        interpreter.execute(ast)
    return f.getvalue().strip()


def macro_returning(body_line: str) -> str:
    """构造一个把块内容作为整体返回的宏"""
    return (
        "定义宏 取值(块)\n"
        "    返回 引述\n"
        "        定义 x = $块\n"
        "        x\n"
        "定义 r = !取值()\n"
        f"    {body_line}\n"
        "打印(r)\n"
    )


class TestMacroListReturn:
    def test_multi_element_list_returned_whole(self):
        """[1, 2, 3] 不再被压成最后一个元素 3"""
        assert run(macro_returning("[1, 2, 3]")) == "[1, 2, 3]"

    def test_single_element_list_not_unwrapped(self):
        """单元素列表 [42] 保持为列表，不再被拆成标量 42"""
        assert run(macro_returning("[42]")) == "[42]"

    def test_scalar_return_unaffected(self):
        """标量返回值仍正常"""
        assert run(macro_returning("7")) == "7"

    def test_nested_list_returned_whole(self):
        """嵌套列表作为整体返回"""
        assert run(macro_returning("[[1, 2], [3, 4]]")) == "[[1, 2], [3, 4]]"


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
