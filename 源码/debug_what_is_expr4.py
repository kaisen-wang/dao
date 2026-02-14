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

# 解析到 pos=33 (数值 '0')
for i in range(33):
    stmt = parser.parse_statement()
    if stmt:
        print(f"  Statement {i}: {type(stmt).__name__}")

print()
print(f"=== Now at pos {parser.pos} ===")
print(f"  Token: {parser.current.type.name}")

# 调用 parse_statement() 来解析 '设 总和 = 0'
stmt = parser.parse_statement()
if stmt:
    print()
    print(f"  Statement 34: {type(stmt).__name__}")
    if hasattr(stmt, "name") and hasattr(stmt, "value"):
        print(f"    Name: {stmt.name}")
        if hasattr(stmt.value, "value"):
            print(f"    Value: {stmt.value.value}")

print()
print(f"=== Now at pos {parser.pos} ===")
print(f"  Token: {parser.current.type.name}")

# 解析下一个语句 !循环(5) { ... }
stmt = parser.parse_statement()
if stmt:
    print()
    print(f"  Statement 35: {type(stmt).__name__}")

    if hasattr(stmt, "expression") and isinstance(stmt.expression, MacroCall):
        print(f"    Expression: {type(stmt.expression).__name__}")
        print(f"    Arguments: {len(stmt.expression.arguments)}")

        for j, arg in enumerate(stmt.expression.arguments):
            print(f"      Arg {j}: {type(arg).__name__}")

            if isinstance(arg, BlockExpr):
                print(f"      Block body: {len(arg.body)} statements")
                for i, s in enumerate(arg.body):
                    print(f"        Statement {i}: {type(s).__name__}")

                    # 打印详细的语句信息
                    if hasattr(s, "__dict__"):
                        for k, v in s.__dict__.items():
                            if not k.startswith("__"):
                                print(
                                    f"          {k}: {type(v).__name__ if hasattr(v, '__dict__') else repr(v)}"
                                )

print()
print(f"=== Final position {parser.pos} ===")
if parser.pos < len(parser.tokens):
    print(
        f"  Next token: {tokens[parser.pos].type.name} -> '{tokens[parser.pos].value}'"
    )
