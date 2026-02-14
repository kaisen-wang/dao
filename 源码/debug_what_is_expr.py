from dao.lexer.core import Lexer
from dao.parser.core import Parser

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

parser = Parser(tokens, code)

print("=== Parsing ===")

# 解析到 pos=35 (感叹号)
for i in range(35):
    parser.parse_statement()

print()
print(f"=== Now at pos {parser.pos} ===")
print(f"  Token: {parser.current.type.name}")

# 调用 parse_statement 后查看 expr
try:
    print()
    print("=== Calling parse_statement() ===")
    stmt = parser.parse_statement()

    print()
    print(f"=== Returned Statement: {type(stmt).__name__} ===")

    if hasattr(stmt, "expression"):
        print(f"  Expression: {type(stmt.expression).__name__}")

        if hasattr(stmt.expression, "arguments"):
            print(f"  Arguments: {len(stmt.expression.arguments)}")
            for arg in stmt.expression.arguments:
                print(f"  Arg type: {type(arg).__name__}")

    if hasattr(stmt, "body"):
        print(f"  Body statements: {len(stmt.body)}")
        for i, s in enumerate(stmt.body):
            print(f"    Statement {i}: {type(s).__name__}")

except Exception as e:
    print()
    print(f"=== ERROR ===")
    print(f"{type(e).__name__}: {e}")
    import traceback

    print()
    print("Stack trace:")
    print(traceback.format_exc())

print()
print(f"=== Final position: {parser.pos} ===")
if parser.pos < len(parser.tokens):
    print(f"  Next token: {parser.current.type.name} -> '{parser.current.value}'")
