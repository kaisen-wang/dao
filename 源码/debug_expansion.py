"""
调试宏展开过程脚本
"""

import os
import sys

# 确保能导入dao包
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dao.interpreter import Interpreter
from dao.lexer import Lexer
from dao.macros import MacroExpander
from dao.macros.ast_repr import DataToAST
from dao.macros.registry import find_macro
from dao.parser import Parser


def debug_expansion():
    """调试宏展开过程"""
    code = """
定义宏 循环(n, 块) {
    返回 引述 {
        设 i = 0
        当 i < $n {
            $块
            i = i + 1
        }
    }
}

设 总和 = 0
!循环(5) {
    总和 = 总和 + i
}
"""

    interpreter = Interpreter()

    # 1. 词法分析
    lexer = Lexer(code, "<调试>")
    tokens = lexer.tokenize()

    # 2. 语法分析
    parser = Parser(tokens, code)
    ast = parser.parse()

    # 获取宏定义
    macro_info = find_macro("循环")
    print("=== 找到的宏信息 ===")
    print(macro_info)
    print()

    # 重建参数
    from dao.ast_nodes import NumberLiteral

    n_arg = NumberLiteral(1, 0, 5)

    # 从 AST 中找到块参数
    block_arg = None
    for stmt in ast.statements:
        if hasattr(stmt, "expression") and hasattr(stmt.expression, "arguments"):
            for arg in stmt.expression.arguments:
                if hasattr(arg, "body"):
                    block_arg = arg
            break

    print("=== 找到的块参数 ===")
    print(block_arg)
    print()

    # 应用参数
    expander = MacroExpander()
    expanded = expander._apply_macro_parameters(
        macro_info.body, macro_info.parameters, [n_arg, block_arg]
    )
    expanded = expander.expand(expanded)

    print("=== 宏展开后 === ")
    print(type(expanded).__name__)
    print(expanded)
    print()


debug_expansion()
