"""
调试宏展开过程
"""

import sys

sys.path.insert(0, "E:\\data\\code\\dao\\源码")

from dao.ast_nodes import MacroCall
from dao.interpreter import Interpreter
from dao.lexer import Lexer
from dao.macros.expander import MacroExpander
from dao.parser import Parser


def debug_expansion():
    """调试宏展开过程"""
    code = """
定义宏 可选参数(x, y=10) {
    返回 引述 {
        $x + $y
    }
}

设 结果1 = !可选参数(5)
"""

    lexer = Lexer(code, "<调试>")
    tokens = lexer.tokenize()

    parser = Parser(tokens, code)
    ast = parser.parse()

    print("=== 解析后的 AST ===")
    print(ast)

    # 找到第一个宏调用
    macro_call = None
    for stmt in ast.statements:
        if hasattr(stmt, "value") and isinstance(stmt.value, MacroCall):
            macro_call = stmt.value
            break

    if not macro_call:
        print("未找到宏调用")
        return

    print("\n=== 宏调用信息 ===")
    print(f"宏名称: {macro_call.name}")
    print(f"参数数量: {len(macro_call.arguments)}")
    for i, arg in enumerate(macro_call.arguments):
        print(f"参数 {i}: {arg} ({type(arg)})")

    # 检查宏注册表
    from dao.macros.registry import MacroRegistry

    registry = MacroRegistry()

    print("\n=== 宏注册表 ===")
    print(f"所有已注册的宏: {registry.list_macros()}")

    macro_info = registry.find_macro(macro_call.name)
    print(f"找到宏: {macro_info}")

    if macro_info:
        print(f"宏参数: {macro_info.parameters}")
        print(f"宏体类型: {type(macro_info.body)}")
        print(f"宏体: {macro_info.body}")

    # 尝试手动展开
    print("\n=== 手动执行宏展开 ===")
    expander = MacroExpander()

    # 手动执行参数替换
    from dao.ast_nodes import (
        BinaryOp,
        Identifier,
        NumberLiteral,
        QuoteBlock,
        UnquoteExpr,
    )

    # 检查参数是否被正确处理
    if hasattr(macro_info.body, "body"):
        print(f"宏体内容: {macro_info.body.body}")
        print(f"宏体body类型: {type(macro_info.body.body)}")

        if macro_info.body.body:
            first_stmt = macro_info.body.body[0]
            print(f"第一个语句: {first_stmt}")
            print(f"类型: {type(first_stmt)}")

            if hasattr(first_stmt, "expression"):
                expr = first_stmt.expression
                print(f"表达式: {expr}")
                print(f"左操作数: {expr.left}")
                print(f"右操作数: {expr.right}")

    expanded = expander._apply_macro_parameters(
        macro_info.body, macro_info.parameters, macro_call.arguments
    )

    print("\n=== 替换后的宏体 ===")
    print(expanded)


if __name__ == "__main__":
    debug_expansion()
