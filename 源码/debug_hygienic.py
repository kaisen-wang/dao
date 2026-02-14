"""
调试 test_hygienic_macro 测试
"""

import sys

sys.path.insert(0, "E:\\data\\code\\dao\\源码")

from dao.lexer import Lexer
from dao.tokens import TokenType
from dao.parser import Parser
from dao.interpreter import Interpreter


def debug_hygienic_test():
    """调试卫生宏测试"""
    code = """
定义宏 卫生测试(x) {
    返回 引述 {
        设 temp = $x * 2
        temp
    }
}

设 temp = 10
设 结果 = !卫生测试(5)
"""

    print("=== 开始调试 ===")

    # 词法分析
    print("\n1. 词法分析阶段:")
    lexer = Lexer(code, "<测试>")
    tokens = lexer.tokenize()
    for i, token in enumerate(tokens):
        print(
            f"  {i:2d}: {token.type.name} -> '{token.value}' (Line={token.line}, Column={token.column})"
        )

    # 语法分析
    print("\n2. 语法分析阶段:")
    parser = Parser(tokens, code)
    ast = parser.parse()

    print(f"Program statements: {len(ast.statements)}")
    for stmt in ast.statements:
        print(f"  Statement type: {type(stmt).__name__}")

    # 执行代码
    print("\n3. 执行阶段:")
    interpreter = Interpreter()
    result = interpreter.execute(ast, source=code)
    print(f"Execution result: {result}")
    print(f"Global environment:")
    for name, value in interpreter.global_env.values.items():
        print(f"  {name}: {value}")


if __name__ == "__main__":
    try:
        debug_hygienic_test()
    except Exception as e:
        print(f"\n错误: {type(e).__name__}: {e}")
        import traceback

        import traceback
        print(f"\n堆栈跟踪: {traceback.format_exc()}")
