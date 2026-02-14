from dao.interpreter.core import Interpreter
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
print("=== Tokenization ===")
for i, t in enumerate(tokens):
    print(f"{i}: {t.type.name} -> '{t.value}'")

# 创建解析器
parser = Parser(tokens, code)
print()
print("=== Parsing ===")

try:
    parser.pos = 34
    while parser.current.type != parser.tokens[-1].type:
        print(f"\npos={parser.pos}")
        print(f"  Token: {parser.current.type.name} -> '{parser.current.value}'")

        if parser.current.type.name == "感叹号" and parser.peek().type.name == "标识符":
            print("  [Calling] parse_macro_call()")
            macro_call = parser.parse_macro_call()
            print("  [Success] parse_macro_call()")
            print(f"    name: {macro_call.name}")
            print(f"    args: {len(macro_call.arguments)} arguments")
            print("  [MACRO CALL STRUCTURE]")
            print(repr(macro_call))
            print("  =======================")
        else:
            print("  [Calling] parse_statement()")
            stmt = parser.parse_statement()
            if stmt:
                print(f"  [Success] parse_statement() returned: {type(stmt).__name__}")
            else:
                print("  [None] parse_statement()")

except Exception as e:
    print()
    print("=== ERROR ===")
    print(f"{type(e).__name__}: {e}")
    import traceback

    print()
    print("Stack trace:")
    print(traceback.format_exc())

print()
print("=== Final position ===")
print(f"pos={parser.pos}")
if parser.pos < len(parser.tokens):
    print(
        f"Current token: {parser.tokens[parser.pos].type.name} -> '{parser.tokens[parser.pos].value}'"
    )
