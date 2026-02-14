from dao.lexer import Lexer
from dao.parser import Parser

code = """
当 i < $n {
    $块
    i = i + 1
}
"""

lexer = Lexer(code)
tokens = list(lexer.tokenize())

print("=== Token List ===")
for i, t in enumerate(tokens):
    print(f"{i:2d} | {t.type.name} -> {repr(t.value)}")

parser = Parser(tokens, code)

while parser.pos < len(tokens) and tokens[parser.pos].type != tokens[-1].type:
    t = tokens[parser.pos]
    print()
    print(f"parse at {parser.pos}")
    stmt = parser.parse_statement()
    print(f"Stmt type: {type(stmt).__name__}")

    if hasattr(stmt, "body"):
        print(f"Body: {len(stmt.body)} statements")
        for i, s in enumerate(stmt.body):
            print(f"  Statement {i}: {type(s).__name__}")

            if hasattr(s, "name"):
                print(f"    Name: {s.name}")

            if hasattr(s, "target") and hasattr(s.target, "name"):
                print(f"    Target: {s.target.name}")

            if hasattr(s, "value"):
                print(f"    Value: {type(s.value).__name__}")
