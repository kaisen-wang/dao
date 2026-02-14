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

# 找出感叹号 token 的位置
exclamation_pos = None
for i, t in enumerate(tokens):
    if t.type.name == "感叹号":
        exclamation_pos = i
        break

if exclamation_pos is not None:
    print("=== Exclamation Mark Token ===")
    print(f"Position: {exclamation_pos}")
    print(f"Token type: {tokens[exclamation_pos].type.name}")
    print(f"Token value: '{tokens[exclamation_pos].value}'")
    print(
        f"Next token: {tokens[exclamation_pos + 1].type.name} -> '{tokens[exclamation_pos + 1].value}'"
    )
    print()

parser.pos = exclamation_pos
print("=== Parser.current ===")
print(f"  Type: {parser.current.type.name}")
print(f"  Value: '{parser.current.value}'")

print()
print("=== Parser.peek() ===")
print(f"  Type: {parser.peek().type.name}")
print(f"  Value: '{parser.peek().value}'")

print()
print("=== parse_primary condition ===")
condition = parser.current.type.name == "感叹号" and parser.peek().type.name == "标识符"
print(f"  '{parser.current.type.name} and {parser.peek().type.name}' == {condition}")

print()
if condition:
    print("=== Calling parse_macro_call ===")
    macro_call = parser.parse_macro_call()
    print(f"Success!")
    print(f"Name: '{macro_call.name}'")
    print(f"Arguments: {len(macro_call.arguments)}")
else:
    print("ERROR! parse_primary didn't recognize exclamation mark")

print()
print("=== Final position ===")
print(f"pos: {parser.pos}")
if parser.pos < len(tokens):
    print(
        f"Current token: {tokens[parser.pos].type.name} -> '{tokens[parser.pos].value}'"
    )
else:
    print("Reached EOF")
