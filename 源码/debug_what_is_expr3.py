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

parser = Parser(tokens, code)

print("=== Parsing ===")

for i in range(34):
    stmt = parser.parse_statement()
    if stmt:
        print(f"  Statement {i}: {type(stmt).__name__}")

print()
print(f"=== Now at pos {parser.pos} ===")
print(f"  Token: {parser.current.type.name}")

stmt = parser.parse_statement()

print()
print(f"=== Returned Statement: {type(stmt).__name__} ===")

if hasattr(stmt, "expression") and isinstance(stmt.expression, MacroCall):
    print(f"  Expression: {type(stmt.expression).__name__}")
    print(f"  Arguments: {len(stmt.expression.arguments)}")

    for j, arg in enumerate(stmt.expression.arguments):
        print(f"    Arg {j}: {type(arg).__name__}")

        if isinstance(arg, BlockExpr):
            print(f"    Block body statements: {len(arg.body)}")
            for i, s in enumerate(arg.body):
                print(f"      Statement {i}: {type(s).__name__}")
                if hasattr(s, "__dict__"):
                    for k, v in s.__dict__.items():
                        if not k.startswith("__"):
                            print(
                                f"        {k}: {type(v).__name__ if hasattr(v, '__dict__') else repr(v)}"
                            )

                        # 如果是赋值语句，打印详细信息
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

                        # 如果是变量声明，打印详细信息
                        if hasattr(s, "name") and hasattr(s, "value"):
                            print(f"          Name: {s.name}")
                            if hasattr(s.value, "value"):
                                print(f"          Value: {s.value.value}")

print()
print(f"=== pos after parsing == {parser.pos} ===")
if parser.pos < len(tokens):
    print(
        f"  Next token: {tokens[parser.pos].type.name} -> '{tokens[parser.pos].value}'"
    )
