import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dao.lexer import Lexer
from dao.parser import Parser


def debug_code(source):
    # 词法分析
    lexer = Lexer(source, "<调试>")
    tokens = lexer.tokenize()

    # 语法分析
    parser = Parser(tokens, source)
    ast = parser.parse()
    print(f"AST: {type(ast)}")
    for i, stmt in enumerate(ast.statements):
        print(f"  语句{i}: {type(stmt)}, {stmt}")

    return ast


if __name__ == "__main__":
    source = """
定义宏 加一(x) {
    返回 引述 { $x + 1 }
}

设 结果 = !加一(5)
"""

    print("调试代码解析过程:")
    print("=" * 50)
    print(f"源: {repr(source)}")
    print()
    ast = debug_code(source)
    print()
    print("=" * 50)
    print("语句列表:")
    for i, stmt in enumerate(ast.statements):
        print()
        print(f"  语句{i}: {type(stmt)}")
        print(f"    详细信息: {str(stmt)}")
