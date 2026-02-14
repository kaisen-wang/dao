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

# 创建解析器
parser = Parser(tokens, code)

print("=== Parsing ===")

for i in range(3):
    stmt = parser.parse_statement()
    print(f"  Statement {i}: {type(stmt).__name__}")
    if (
        i == 2
        and hasattr(stmt, "expression")
        and isinstance(stmt.expression, MacroCall)
    ):
        print(f"    Arguments: {len(stmt.expression.arguments)}")
        for j, arg in enumerate(stmt.expression.arguments):
            print(f"      Arg {j}: {type(arg).__name__}")
            if isinstance(arg, BlockExpr):
                print(f"        Block body: {len(arg.body)} statements")
                for k, s in enumerate(arg.body):
                    print(f"          Statement {k}: {type(s).__name__}")
                    if hasattr(s, "target") and hasattr(s, "value"):
                        print(f"            Target: {s.target}")
                        print(f"            Value: {s.value}")

print()
print(f"=== After {i + 1} statements ===")
print(f"pos: {parser.pos}")

# 打印当前 token 信息
if parser.pos < len(tokens):
    token = tokens[parser.pos]
    print(f"Current token: {token.type.name} ({repr(token.value)})")

    if parser.pos + 1 < len(tokens):
        next_token = tokens[parser.pos + 1]
        print(f"Next token: {next_token.type.name} ({repr(next_token.value)})")

print()

# 尝试直接解析块
stmt = parser.parse_statement()

print(f"  Next Statement: {type(stmt).__name__}")

if stmt and hasattr(stmt, "expression") and isinstance(stmt.expression, MacroCall):
    print(f"    Macro call: {stmt.expression.name}")
    print(f"    Arguments: {len(stmt.expression.arguments)}")
    for j, arg in enumerate(stmt.expression.arguments):
        print(f"      Arg {j}: {type(arg).__name__}")
        if isinstance(arg, BlockExpr):
            print(f"        Block body: {len(arg.body)} statements")
            for k, s in enumerate(arg.body):
                print(f"          Statement {k}: {type(s).__name__}")
