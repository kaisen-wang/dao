from dao.interpreter.core import Interpreter
from dao.lexer.core import Lexer
from dao.parser.core import Parser
from dao.tokens import TokenType

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

# 词法分析
lexer = Lexer(code)
tokens = list(lexer.tokenize())
print("=== Tokenization ===")
for i, t in enumerate(tokens):
    print(f"{i}: {t.type.name} -> {repr(t.value)}")
print()

# 语法分析
parser = Parser(tokens, code)

# 打印解析到的每个 token 位置
print("=== Parsing Steps ===")

try:
    # 逐token解析来调试
    while parser.pos < len(tokens) - 1:  # 排除EOF
        if parser.pos >= len(tokens):
            break

        t = tokens[parser.pos]
        print(
            f"pos={parser.pos:2d} | {t.line}:{t.column} | {t.type.name} -> {repr(t.value)}"
        )

        if parser.pos == len(tokens):
            break

        if parser.pos == 0:
            stmt = parser.parse_statement()
            print(
                f"parse_statement returned: {type(stmt).__name__ if stmt else 'None'}"
            )
        else:
            print(f"Calling parse_statement again...")
            stmt = parser.parse_statement()
            print(
                f"parse_statement returned: {type(stmt).__name__ if stmt else 'None'}"
            )

        print()
except Exception as e:
    print(f"=== ERROR ===")
    print(f"{type(e).__name__}: {e}")
    import traceback

    print(traceback.format_exc())

print(f"Final position: {parser.pos}")
print(f"Current token: {tokens[parser.pos]}")
