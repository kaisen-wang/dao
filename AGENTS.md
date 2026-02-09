# AGENTS.md - 道语言解释器开发指南

此文件为参与道语言解释器开发的AI代理提供项目规范。

## 开发环境

- Python >= 3.10
- 工作目录：`源码/` (所有开发工作在此目录下进行)

## 命令参考

```bash
cd 源码                    # 进入源码目录
pip install -r requirements.txt  # 安装依赖
python main.py             # 启动REPL
python main.py examples/你好世界.道  # 执行.道文件
pytest tests/ -v           # 运行所有测试
pytest tests/test_lexer.py -v     # 运行单个测试文件
pytest tests/test_lexer.py::TestLexerBasics::test_empty_source -v  # 单个测试
ruff check .               # 代码检查
```

## 代码风格

### 命名约定

- 类名：英文命名，如 `Lexer`, `Parser`, `Environment`, `DaoClass`
- 函数/方法名：英文命名，如 `tokenize()`, `parse()`, `execute()`
- 变量名：英文，如 `self.pos`, `self.tokens`
- 常量：全大写英文，如 `KEYWORDS`, `EOF`
- 异常类：中文命名，如 `词法错误`, `语法错误`, `运行时错误`

### 文件组织

```
dao/
├── tokens.py            # TokenType枚举 + Token数据类
├── ast_nodes.py         # AST节点定义
├── environment.py       # 作用域管理
├── errors.py           # 自定义异常类层次
├── lexer/              # 词法分析器
│   ├── core.py         # 主类 + 基础设施
│   └── readers.py      # Token读取方法
├── parser/             # 语法分析器
│   ├── core.py         # 主类 + 基础设施
│   ├── statements.py   # 语句解析
│   └── expressions.py  # 表达式解析
├── interpreter/        # 解释器
│   ├── core.py         # 主类 + 入口
│   ├── statements.py   # 语句执行
│   └── expressions.py  # 表达式求值
└── builtins/           # 内置函数
    ├── callables.py    # 可调用基类
    ├── functions.py    # 基础内置函数
    ├── oop_types.py    # OOP类型实现
    └── hof.py          # 高阶函数
```

### 导入风格

```python
# 标准库导入
import sys
from typing import Any
# dao包内相对导入
from ..tokens import Token, TokenType, KEYWORDS
from ..errors import 词法错误
from .readers import LexerReaders
```

### 类型注解

使用Python 3.10+联合类型语法：`Type1 | Type2`，例如：`parent: "Environment | None" = None`

### AST节点定义

所有AST节点使用`@dataclass`，包含位置信息：

```python
@dataclass
class Expression(ASTNode):
    """表达式基类"""
    line: int = 0
    column: int = 0

@dataclass
class BinaryOp(Expression):
    """二元运算"""
    left: Expression
    operator: str
    right: Expression
```

### 错误处理

使用自定义异常层次，必须包含位置信息：

```python
class 道错误(Exception):
    def __init__(self, message: str, line: int = 0, column: int = 0):
        self.message = message
        self.line = line
        self.column = column

def raise_error(self, message: str):
    raise 语法错误(message, self.line, self.column)
```

### 测试规范

- 使用pytest
- 测试类以`Test`开头，方法以`test_`开头
- 测试文件使用`sys.path.insert(0, ...)`来导入源码：
```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dao.lexer import Lexer
from dao.tokens import TokenType
```
- 使用辅助函数简化测试：
```python
def parse(source: str) -> Program:
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse()

class TestParserVariables:
    def test_variable_decl(self):
        ast = parse("定义 x = 42\n")
        assert len(ast.statements) == 1
```
- 带覆盖率测试：`pytest tests/ -v --cov=dao --cov-report=term-missing`

## 项目架构

道语言采用三阶段处理流程：

1. **词法分析** (Lexer)：源代码 → Token流
   - 缩进处理为隐式标记(INDENT/DEDENT)
   - 支持中文关键字和标点

2. **语法分析** (Parser)：Token流 → AST
   - 递归下降策略
   - 运算符优先级通过方法调用层级实现

3. **解释执行** (Interpreter)：AST → 执行结果
   - 树遍历解释器
   - 词法作用域管理

## 中文关键字列表

常用关键字：定义, 常量, 函数, 返回, 如果, 否则如果, 否则, 当, 遍历, 在, 匹配, 情况, 尝试, 捕获, 类型, 继承自, 初始化, 本对象, 父对象

## 注意事项

- 所有用户可见的错误消息必须使用中文
- 保持AST节点的不可变性(frozen=True或避免修改)
- 新增语法特性时需同步更新：tokens.py, ast_nodes.py, lexer/, parser/, interpreter/, tests/
- 测试覆盖率目标：每个新特性至少3个测试用例
