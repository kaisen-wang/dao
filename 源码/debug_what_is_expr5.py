from dao.ast_nodes import BlockExpr, MacroCall
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

print("=== Token List ===")
for i, t in enumerate(tokens):
    print(f"{i:2d} | {t.line:2d}:{t.column:2d} | {t.type.name:10} | '{t.value}'")

# 创建解析器
parser = Parser(tokens, code)

print()
print("=== Parsing ===")

# 解析到 pos=34（换行）
for i in range(34):
    stmt = parser.parse_statement()
    if stmt:
        print(f"  Statement {i}: {type(stmt).__name__}")

print()
print(f"=== After {i} statements ===")
print(f"  Current pos: {parser.pos}")

# 解析 !循环(5) { ... } 语句
stmt = parser.parse_statement()

print()
print(f"=== Statement Parsed ===")
print(f"  Type: {type(stmt).__name__}")

if hasattr(stmt, "expression") and isinstance(stmt.expression, MacroCall):
    print(f"  Macro call: {stmt.expression.name}")
    print(f"  Arguments: {len(stmt.expression.arguments)}")

    for j, arg in enumerate(stmt.expression.arguments):
        print(f"    Arg {j}: {type(arg).__name__}")

        if isinstance(arg, BlockExpr):
            print(f"    Block body statements: {len(arg.body)}")
            for i, s in enumerate(arg.body):
                print(f"      Statement {i}: {type(s).__name__}")
                if hasattr(s, "__dict__"):
                    for k, v in s.__dict__.items():
                        if not k.startswith("__") and k not in ["line", "column"]:
                            print(f"        {k}: {v}")

                        if hasattr(s, "target") and hasattr(s, "value"):
                            if hasattr(s.target, "name"):
                                print(f"          Target: {s.target.name}")
                            if (
                                hasattr(s.value, "left")
                                and hasattr(s.value, "operator")
                                and hasattr(s.value, "right")
                            ):
                                if hasattr(s.value.left, "name"):
                                    print(f"          Left: {s.value.left.name}")
                                print(f"          Op: {s.value.operator}")
                                if hasattr(s.value.right, "name"):
                                    print(f"          Right: {s.value.right.name}")
                                if hasattr(s.value.right, "value"):
                                    print(f"          Right: {s.value.right.value}")

print()
print(f"=== Final position {parser.pos} ===")
if parser.pos < len(parser.tokens):
    print(
        f"  Next token: {tokens[parser.pos].type.name} -> '{tokens[parser.pos].value}'"
    )
