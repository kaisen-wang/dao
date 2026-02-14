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

# 查找包含 "}" 的 tokens
print("=== Tokenization with Context ===")
for i, t in enumerate(tokens):
    if i == 46:  # 问题位置
        print(f"  === Position {i} === ")

    prev = (
        f"{tokens[i - 1].type.name} -> {repr(tokens[i - 1].value)}"
        if i > 0
        else "START"
    )
    curr = f"{t.type.name} -> {repr(t.value)}"
    next_ = (
        f"{tokens[i + 1].type.name} -> {repr(tokens[i + 1].value)}"
        if i < len(tokens) - 1
        else "END"
    )

    line_info = f"pos={i:2d} | {t.line}:{t.column} | {prev:30} | {curr:25} | {next_}"

    if i == 46:
        print(line_info + " <-- ISSUE HERE")
    else:
        print(line_info)

# 现在尝试解析
print()
print("=== Parsing ===")
try:
    parser = Parser(tokens, code)
    parser.pos = 35
    print(f"pos={parser.pos}, current token: {repr(tokens[35].value)}")
    macro_call = parser.parse_macro_call()
    print(f"macro_call parsed successfully")
    print(f"name: {macro_call.name}")
    print(f"args: {len(macro_call.arguments)} arguments")

except Exception as e:
    print("ERROR in parsing macro call:")
    print(f"  {type(e).__name__}: {e}")

    import traceback

    print(traceback.format_exc())
