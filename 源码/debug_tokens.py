"""
调试工具：打印词法分析后的 Token 序列
"""

import sys

sys.path.insert(0, "E:\\data\\code\\dao\\源码")

from dao.lexer import Lexer
from dao.tokens import TokenType


def print_tokens(code):
    """打印词法分析后的 Token 序列"""
    lexer = Lexer(code, "<调试>")
    tokens = lexer.tokenize()

    print("Token 序列:")
    for i, token in enumerate(tokens):
        print(
            f"  {i:2d}: Type={token.type.name}, Value={repr(token.value)}, Line={token.line}, Column={token.column}"
        )

    return tokens


if __name__ == "__main__":
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

    print_tokens(code)
