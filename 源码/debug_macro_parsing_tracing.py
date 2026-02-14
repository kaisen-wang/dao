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

# 创建解析器
parser = Parser(tokens, code)
parser.pos = 35

# 手动跟踪 parse_macro_call 过程
print("=== Step by Step Macro Call Parsing ===")
print(f"Current position: {parser.pos}")

# 检查当前 token 是感叹号
print()
print("=== Step 1: ! ===")
token = tokens[parser.pos]
assert token.type.name == "感叹号"
print(f"  [OK] Current token is '!'")
parser.pos += 1

# 检查下一个 token 是标识符
print()
print("=== Step 2: name ===")
token = tokens[parser.pos]
assert token.type.name == "标识符"
name = token.value
print(f"  [OK] Macro name: '{name}'")
parser.pos += 1

# 检查左括号
print()
print("=== Step 3: ( ===")
token = tokens[parser.pos]
assert token.type.name == "左括号"
print(f"  [OK] Left parenthesis")
parser.pos += 1

# 解析参数
print()
print("=== Step 4: argument ===")
token = tokens[parser.pos]
assert token.type.name == "数值"
value = token.value
print(f"  [OK] Argument value: {value}")
parser.pos += 1

# 检查右括号
print()
print("=== Step 5: ) ===")
token = tokens[parser.pos]
assert token.type.name == "右括号"
print(f"  [OK] Right parenthesis")
parser.pos += 1

# 检查左花括号 - 这是我们需要解析的块
print()
print("=== Step 6: { ===")
token = tokens[parser.pos]
print(f"  Current token: {token.type.name} -> '{token.value}'")
if token.type.name == "左花括号":
    print("  [OK] Left curly brace for block")
    parser.pos += 1
else:
    print(f"  ERROR! Expected '{{', got '{token.type.name}': '{token.value}'")

# 解析块内容
print()
print("=== Step 7: block content ===")
block = []
while parser.pos < len(tokens):
    token = tokens[parser.pos]
    if token.type.name == "右花括号":
        break

    print(f"  Token at pos {parser.pos}: {token.type.name} -> '{token.value}'")

    parser.pos += 1

print(f"  [OK] Block parsing completed")

# 检查匹配的右花括号
print()
print("=== Step 8: } ===")
token = tokens[parser.pos]
if token.type.name == "右花括号":
    print("  [OK] Right curly brace for block")
    parser.pos += 1
else:
    print(f"  ERROR! Expected '}}', got '{token.type.name}': '{token.value}'")

# 打印最后的位置
print()
print("=== Final position: pos =", parser.pos)
print(f"Remaining tokens count: {len(tokens) - 1 - parser.pos}")
print()
print(f"=== Token list from pos {parser.pos} to end ===")
for i in range(parser.pos, len(tokens)):
    t = tokens[i]
    print(f"  pos={i} | {t.line}:{t.column} | {t.type.name} -> '{t.value}'")
