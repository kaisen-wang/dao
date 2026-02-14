"""
调试宏展开过程脚本2
"""

import os
import sys

# 确保能导入dao包
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dao.interpreter import Interpreter
from dao.lexer import Lexer
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

    # 打印完整的 AST
    print("=== 完整 AST ===")
    print("=" * 60)

    for i, stmt in enumerate(ast.statements):
        print(f"\n=== 语句 {i} ===")
        print(stmt.__class__.__name__)
        print(stmt)

        if hasattr(stmt, "parameters"):
            print(f"参数: {stmt.parameters}")

        if hasattr(stmt, "body"):
            print(f"Body: {len(stmt.body)} 语句")
            for j, b_stmt in enumerate(stmt.body):
                print(f"  子语句 {j}:")
                print(f"    类型: {type(b_stmt).__name__}")
                print(f"    内容: {b_stmt}")

                # 检查是否有引号块
                if hasattr(b_stmt, "value"):
                    print(f"    值类型: {type(b_stmt.value).__name__}")
                    if hasattr(b_stmt.value, "body"):
                        print(f"    块体: {len(b_stmt.value.body)} 语句")
                        for k, q_stmt in enumerate(b_stmt.value.body):
                            print(f"      块子语句 {k}:")
                            print(f"        类型: {type(q_stmt).__name__}")
                            print(f"        内容: {q_stmt}")

                            if hasattr(q_stmt, "body"):
                                print(f"        块子语句 Body: {len(q_stmt.body)} 语句")
                                for l, qq_stmt in enumerate(q_stmt.body):
                                    print(f"          块子子语句 {l}:")
                                    print(f"            类型: {type(qq_stmt).__name__}")
                                    print(f"            内容: {qq_stmt}")


debug_expansion()
