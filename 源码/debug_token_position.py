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

for i, t in enumerate(tokens):
    print(f"{i:2d} | {t.line:2d}:{t.column:2d} | {t.type.name:10} | '{t.value}'")

print()
print("=== Target positions ===")
target_names = ["感叹号", "左花括号", "标识符", "右花括号"]
for i, t in enumerate(tokens):
    if t.type.name in target_names:
        print(f"  {t.type.name}: {i}")
