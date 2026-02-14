from dao.lexer import Lexer
from dao.parser.core import Parser

code = """
!循环(5) {
    总和 = 总和 + i
}
"""

lexer = Lexer(code)
tokens = list(lexer.tokenize())

print("=== Token List ===")
for i, t in enumerate(tokens):
    print(f"{i:2d} | {t.type.name} -> {repr(t.value)}")

parser = Parser(tokens, code)

stmt = parser.parse_statement()
print(f"\n=== Parsed Statement ===")
print(f"Type: {type(stmt).__name__}")

if hasattr(stmt, "expression"):
    print(f"Expression: {type(stmt.expression).__name__}")

    if hasattr(stmt.expression, "arguments"):
        print(f"Arguments: {len(stmt.expression.arguments)}")
        for j, arg in enumerate(stmt.expression.arguments):
            print(f"  Arg {j}: {type(arg).__name__}")
            from dao.ast_nodes import BlockExpr

            if isinstance(arg, BlockExpr):
                print(f"    Block body: {len(arg.body)} statements")
                for s in arg.body:
                    print(f"      Statement: {type(s).__name__}")
