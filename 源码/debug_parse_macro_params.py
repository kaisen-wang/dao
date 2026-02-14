#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试宏参数解析
"""

import os
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dao.lexer import Lexer
from dao.parser import Parser


def debug_macro_params():
    code = """
定义宏 可选参数(x, y=10) {
    返回 引述 {
        $x + $y
    }
}
"""

    try:
        print("=== 词法分析 ===")
        lexer = Lexer(code, "<测试>")
        tokens = lexer.tokenize()

        print("=== 语法分析 ===")
        parser = Parser(tokens, code)
        ast = parser.parse()

        print("=== 宏定义信息 ===")
        from dao.ast_nodes import MacroDefinition

        macro_def = None
        for stmt in ast.statements:
            if isinstance(stmt, MacroDefinition):
                macro_def = stmt
                break

        if macro_def:
            print(f"  宏名: {macro_def.name}")
            print(f"  参数: {macro_def.parameters}")
            print(f"  参数类型: {[type(p).__name__ for p in macro_def.parameters]}")
            print(f"  函数体长度: {len(macro_def.body)}")

            if len(macro_def.body) > 0:
                print(f"  函数体: {type(macro_def.body[0])}")

        print("\n=== 完整的 AST ===")
        print(ast)
        return True

    except Exception as e:
        print(f"=== 错误: {type(e).__name__} ===")
        print(f"{e}")
        import traceback

        print(f"堆栈跟踪: {traceback.format_exc()}")
        return False


if __name__ == "__main__":
    print("调试宏参数解析")
    print("-" * 40)
    print()
    debug_macro_params()
