#!/usr/bin/env python3
"""调试宏解析器 - 详细信息"""

from dao.lexer import Lexer
from dao.parser import Parser
from dao.tokens import TokenType


def debug_parse(code):
    print("=== 待解析代码 ===")
    print(code)
    print("\n=== 词法分析 ===")
    lexer = Lexer(code)
    tokens = list(lexer.tokenize())
    for i, token in enumerate(tokens):
        print(
            f"{i:02d}: {token.type.name}({repr(token.value)}) at {token.line}:{token.column}"
        )

    print("\n=== 语法分析 ===")
    parser = Parser(tokens, code)

    print("\n=== parse_macro_definition 执行前状态 ===")
    print(f"当前位置: {parser.current}")
    print(f"下一个: {parser.peek()}")

    try:
        ast = parser.parse()
        print("\n解析成功!")
        print(f"AST类型: {type(ast)}")

        print("\n=== 程序结构 ===")
        print("程序由以下语句组成:")
        for stmt in ast.statements:
            print(f"- {type(stmt).__name__}")

        print("\n=== 宏定义 ===")
        for stmt in ast.statements:
            if hasattr(stmt, "name") and hasattr(stmt, "parameters"):
                print(f"宏: {stmt.name}({', '.join(stmt.parameters)})")

        print("\n=== 打印 AST ===")
        print(ast)

    except Exception as e:
        print(f"\n解析错误: {e}")
        import traceback

        print("\n=== 堆栈信息 ===")
        traceback.print_exc()

    print("\n=== 解析器状态 ===")
    print(f"最后处理的标记位置: {parser.current.line}:{parser.current.column}")
    print(f"最后处理的标记类型: {parser.current.type.name}")
    print(f"最后处理的标记值: {repr(parser.current.value)}")


test_code = """定义宏 注入宏() {
    设 a = 1
    设 b = 2
    返回 引述 { $a + $b }
}

设 注入结果 = !注入宏()
"""

debug_parse(test_code)
