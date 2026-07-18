# AGENTS.md — 道语言解释器

中文多范式编程语言的 Python 解释器。所有开发在 `源码/` 下进行。

## 命令（均在 `源码/` 下运行）

```bash
cd 源码
pip install -r requirements.txt  # pytest, pytest-cov, ruff, prompt-toolkit
python -m venv .venv && source .venv/bin/activate  # 需要 Python 3.10+
python main.py                         # REPL
python main.py examples/你好世界.道     # 文件执行
python main.py --mode vm examples/你好世界.道  # 字节码 VM 模式
python main.py --mode vm --jit --disasm examples/斐波那契.道  # JIT + 反汇编
pytest tests/ -v                      # 全部测试
pytest tests/test_lexer.py::TestLexerBasics::test_empty_source -v  # 单个
pytest tests/ -v --cov=dao --cov-report=term-missing  # 覆盖率
ruff check .
ruff fix .
```

## 架构

- **三阶段流程**: `源代码 → Lexer (Token流) → Parser (AST) → Interpreter (结果)`
- **双执行模式**: 默认 AST 树遍历；`--mode vm` 经 `BytecodeCompiler` → `VirtualMachine` (+ JIT)
- **Parser Mixin**: `Parser` 多重继承自 `StatementParser`（组合 `dao/parser/modules/` 下 13 个子解析器） + `ExpressionParser` + `MacroParser` + `LogicProgrammingParser`
- **Interpreter Mixin**: 继承自 `StatementExecutor` + `ExpressionEvaluator` + `ConcurrencyEvaluator`
- **重大功能包**: `dao/logic/`（逻辑引擎），`dao/macros/`（宏系统），`dao/concurrency/`（通道/协程/原子），`dao/bytecode/` + `dao/vm/` + `dao/jit/`（VM 路线）
- **代码块基于缩进**: 无花括号，Lexer 生成 INDENT/DEDENT 隐式 Token

## 关键约定

- **异常类用中文**: `词法错误`, `语法错误`, `运行时错误`, `类型错误`, `名称错误` 等（`dao/errors.py`）
- **AST 节点**: `@dataclass` 不可变，含 `line`/`column` 位置信息
- **所有用户可见错误消息必须使用中文**
- **文件扩展名**: `.道`
- **新增语法特性同步顺序**: `tokens.py` → `ast_nodes.py` → `lexer/` → `parser/` → `interpreter/` → `tests/`

## 测试规范

- 测试文件均使用 `sys.path.insert(0, ...)` 导入源（非项目安装）：

```python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
```

- 每个新特性至少 3 个测试用例
- 通用辅助函数模式：

```python
# 解析器测试: 源代码 → AST
def parse(source: str) -> Program:
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse()

# 解释器测试: 源代码 → 执行结果
def run(source: str) -> object:
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    return Interpreter().execute(ast)

def capture_output(source: str) -> str:
    from io import StringIO
    from contextlib import redirect_stdout
    f = StringIO()
    with redirect_stdout(f):
        run(source)
    return f.getvalue()
```

- 集成测试 `test_integration.py` 以 subprocess 运行 `.道` 示例文件
- 大型测试目录: `tests/logic_programming/`、`tests/module_system/`、`tests/test_stdlib/`
