#!/usr/bin/env python3
"""
调试引述块解析
"""

import os
import sys

# 确保能导入dao包
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dao.errors import 道错误
from dao.lexer import Lexer
from dao.parser import Parser


def debug_parse():
    """调试解析过程"""
    code = """
定义宏 测试(x) {
    返回 引述 { $x + 1 }
}
"""

    print("源代码:")
    print(code)
    print()

    # 1. 词法分析
    lexer = Lexer(code, "<调试>")
    try:
        tokens = lexer.tokenize()
        print("词法分析结果:")
        for i, token in enumerate(tokens):
            print(
                f"{i:2d} {token.type.name} ({repr(token.value)}) 行:{token.line} 列:{token.column}"
            )

        # 2. 语法分析
        parser = Parser(tokens, code)
        print()
        print("语法分析开始...")
        ast = parser.parse()
        print("语法分析成功!")
        print(ast)

    except 道错误 as e:
        print(f"\n❌ 错误: {e}")
    except Exception as e:
        print(f"\n❌ 未预期的错误: {type(e).__name__}: {e}")
        import traceback

        print(traceback.format_exc())


if __name__ == "__main__":
    debug_parse()
