"""
调试宏系统脚本
"""

import os
import sys

# 确保能导入dao包
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dao.interpreter import Interpreter
from dao.lexer import Lexer
from dao.parser import Parser


def debug_code(source: str, filename: str = "<调试>"):
    """调试一段道语言代码"""
    interpreter = Interpreter()

    # 1. 词法分析
    lexer = Lexer(source, filename)
    tokens = lexer.tokenize()

    # 2. 语法分析
    parser = Parser(tokens, source)
    ast = parser.parse()
    print("=== 解析的AST ===")
    print(ast)
    print()

    # 3. 解释执行
    try:
        print("=== 开始执行 ===")
        result = interpreter.execute(ast, source=source)
        print()
        print("=== 执行结果 ===")
        print(result)
        print()
        print("=== 全局环境变量 ===")
        print(interpreter.global_env.values)
    except Exception as e:
        print(f"\n=== 执行出错 ===")
        print(type(e).__name__, str(e))
        import traceback

        print("堆栈跟踪:")
        print(traceback.format_exc())


debug_code("""
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
""")
