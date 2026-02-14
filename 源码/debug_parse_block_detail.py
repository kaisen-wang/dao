"""
调试块解析详情
"""

import sys

sys.path.insert(0, ".")

from dao.lexer import Lexer
from dao.parser import Parser


def debug_parse():
    """调试块解析细节"""
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
    """

    lexer = Lexer(code, "<调试>")
    tokens = lexer.tokenize()

    print("=== tokens ===")
    for i, token in enumerate(tokens):
        print(f"{i:2d} {token.type.name} '{token.value}'")

    print("\n=== parsing ===")
    parser = Parser(tokens, code)

    try:
        parser.debug = True
        ast = parser.parse()

        print("\n=== parsed ===")

        for stmt in ast.statements:
            print(stmt)

            if hasattr(stmt, "body"):
                print(f"  body: {len(stmt.body)}")

                for b_stmt in stmt.body:
                    print(f"  {b_stmt}")

                    if hasattr(b_stmt, "value"):
                        print(f"    value: {type(b_stmt.value).__name__}")

                        if hasattr(b_stmt.value, "body"):
                            print(f"    value.body: {len(b_stmt.value.body)}")

                            for q_stmt in b_stmt.value.body:
                                print(f"    - {q_stmt}")

                                if hasattr(q_stmt, "body"):
                                    print(f"      body: {len(q_stmt.body)}")

                                    for s_stmt in q_stmt.body:
                                        print(
                                            f"      - {type(s_stmt).__name__}: {s_stmt}"
                                        )
    except Exception as e:
        import traceback

        print()
        print(f"ERROR: {e}")
        print()
        print(traceback.format_exc())


debug_parse()
