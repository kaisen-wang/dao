# VM 语义对齐规格（2026-11-28）

## 目标

让 `--mode vm`（含 `--jit`）与 AST 解释器对同一份道语言程序产生一致语义。
**AST 解释器是唯一语义基准**；任何差异以 AST 侧行为为准。已有能力（导入、在/不在、
类/宏/异常、运算符重载的 AST 实现）不得回退。

实测确认的关键差异（`/tmp/vm_diff_probe.py` 21 例，11 例不一致）：
默认参数 / 变长参数 / 关键字参数 / 解构赋值 / 成员与下标赋值 / 断言 / 常量 /
生成器 / 异步函数 / 文本乘小数 / 整除除零 / 展开表达式 / 枚举注解 / 并行语句。

## 总体策略

- 新增**唯一一个新 opcode**：`OpCode.DELEGATE_STMT`，操作数 = AST 语句节点在常量池中的索引，**无栈效应**。
- 编译器把「VM 没有原生等价、但 AST 解释器已完整实现」的语句统一发射 `DELEGATE_STMT`，
  VM 侧复用内嵌 AST 解释器 + 现有桥接环境执行。这样默认参数/变长参数/生成器/异步/解构/
  断言/成员赋值等一次性对齐，且不需要修改 `CodeObject` 或闭包表示。
- 表达式层的同类缺口复用现有 `DELEGATE_EXPR`（已有 opcode），无需新增。
- 枚举注解复用现有 `APPLY_ANNOTATIONS`（已有 opcode），无需新增。
- 常量语义新增 `Frame.constants`，由桥接环境别名到 `Environment.constants`，VM 原生存储指令也检查。

## 文件独占范围（严禁越界修改）

| 代理 | 独占文件 | 禁止修改 |
|---|---|---|
| compiler-dev | `源码/dao/bytecode/compiler.py` | 其余所有源码/测试/文档 |
| vm-runtime-dev | `源码/dao/vm/core.py`、`源码/dao/vm/bridge.py`、`源码/dao/bytecode/frame.py`、`源码/dao/vm/exceptions.py` | 其余所有源码/测试/文档 |
| opcode-jit-dev | `源码/dao/bytecode/opcodes.py`、`源码/dao/bytecode/disassembler.py`、`源码/dao/jit/native.py` | 其余所有源码/测试/文档 |
| tests-dev | 仅新建 `源码/tests/test_vm_alignment_*.py`（可多个） | 产品源码、既有测试、文档 |
| 主代理 | 本文档、`文档/20-项目整体进度.md`、新交付报告、集成与验收 | — |

**所有代理禁止修改 TaskList（任务列表由主代理维护），禁止跑全量 pytest，
禁止提交 git，禁止改别人的文件。** 每个代理只跑自己新增/相关的测试子集。

## 契约细则

### 1. opcode（opcode-jit-dev）

- 在 `OpCode` 末尾新增 `DELEGATE_STMT = auto()`。
- `Disassembler._format_operand` 把它与 `IMPORT_STMT`/`EXPORT_STMT` 同组显示（`类名 + 关键字段`）。
- `dao/jit/native.py` 的 `_DELEGATED_OPS` 加入 `DELEGATE_STMT`，保证含该指令的函数整段回退解释执行。

### 2. 编译器（compiler-dev）

`_compile_statement` 中以下节点改为发射 `DELEGATE_STMT`（操作数 = `_add_constant(stmt, code)`，**不**再编译其子表达式，保证无栈效应）：

- `AssertStmt`、`DestructureAssign`、`YieldStmt`、`TypeAliasDecl`
- `AsyncFunctionDecl`、`ParallelStmt`、`SelectStmt`、`SyncStmt`、`LogicBlock`
- `Assignment` 且 `target` **不是** `Identifier`（成员/下标写入需 setter、可见性、`int(index)` 等 AST 语义）
- `FunctionDecl` 且满足任一条件：`default_values` 非空、`rest_param` 非空、
  `is_exported` 为真、函数体含 `产出`（按 AST `_has_yield` 的递归规则）、
  注解带关键字参数。其余 `FunctionDecl` 保持现有原生编译快路径（JIT 基准不受影响）。
  委托时注解也由 AST 解释器统一应用，不要再发射 `APPLY_ANNOTATIONS`。

`_compile_variable_decl` 中 `is_constant` 或 `is_exported` 的声明改为发射 `DELEGATE_STMT`，让 AST 侧 `exec_variable_decl` 定义常量/登记导出；普通变量仍走原生指令。

`_compile_enum_decl` 在 `STORE_LOCAL` 后若 `stmt.annotations` 非空，发射 `APPLY_ANNOTATIONS`，操作数采用 `(stmt, local_idx)` 常量（与 `_apply_annotations_to_local` 一致）。注意操作数约定是 `(stmt, name_idx)`。

`_compile_expression` 中：

- `FunctionCall` 若 `keyword_args` 非空 → `DELEGATE_EXPR` 整个调用节点（既不编译 callee 也不编译位置参数）。
- `ListLiteral`/`DictLiteral`/`SetLiteral`/`TupleLiteral` 若任一元素（或键/值）是 `SpreadExpr` → `DELEGATE_EXPR` 整个字面量节点。
- `MATCH_PATTERN` 的常量数据从 `(pattern, is_wildcard)` 扩展为 `(pattern, is_wildcard, force_bind)`，
  其中 `force_bind = case.guard is not None and isinstance(case.pattern, Identifier) and not case.is_wildcard`；
  VM 侧兼容二元组旧格式。

`_calculate_stack_size`：新 opcode 均按无栈效应处理（`DELEGATE_STMT` 与 `DELEGATE_EXPR` 不同，后者压一个值）。

### 3. VM 运行时（vm-runtime-dev）

- `Frame` 新增 `constants: set[str]`。
- `bridge.frame_to_environment` 为每个包装层 Environment 设置 `env.constants = frame.constants`（别名同一个集合），
  使 AST `exec_variable_decl(is_constant=True)` / `env.set()` 的常量检查写到 VM 帧上。
  `globals` 层也需要一个持久的常量集合（例如 `VirtualMachine._global_constants`），
  不要把全局常量误写到某个帧；通过 bridge 的可选参数传入即可（保持旧调用签名兼容）。
- `VirtualMachine._dispatch` 新增 `DELEGATE_STMT`：取常量节点，调用
  `interpreter.exec_statement(node, env)`；`env = self._bridge_environment(frame)`；
  委托前后使用 `_wrap_vm_closures` / `_restore_vm_closures`（与 `DELEGATE_EXPR` 一致）；
  `finally` 中调用 `sync_environment(env, frame)`。无栈效应。
- `STORE_LOCAL`/`STORE_NAME`/`STORE_SCOPE_LOCAL` 写入前检查名字是否在对应作用域的 `constants` 中，
  是则抛 `运行时错误(f"常量 '{name}' 不能被重新赋值")`。
- 二元运算对齐 AST `ExpressionEvaluator.eval_binary_op`：
  左值为 `DaoInstance` 且存在 `运算符<符号>` 方法时，调用 AST 的 `_call_method`（只求值右操作数一次）；
  `文本 * 数值` 时 `int(数值)`；`//` 除零抛 `运行时错误("除零错误")`（`/` 已有，保持一致）。
  无法直接复用时委托 AST 解释器求值，但必须避免重复求值副作用。
- 条件跳转（`POP_JUMP_IF_FALSE`/`JUMP_IF_FALSE`）与 `UNARY_NOT` 改用 AST 的
  `_is_truthy`（`Interpreter._is_truthy` 静态方法），不要直接 `not value`。
- `LOAD_INDEX` 对 list/str 的下标先 `int(index)`，越界/非法索引的错误类型与消息向 AST 对齐。
- `_match_pattern` 支持第三个参数 `force_bind`：`Identifier` 模式且 `force_bind` 为真时
  无论外层是否已有同名变量都绑定主体值；`DictPattern` 的键用 AST `eval_expression`
  求值（经桥接环境），不再只接受字面量。
- 未定义变量的 `LOAD_LOCAL`/`LOAD_NAME` 抛 `名称错误`（统一中文消息），与 AST 一致。

### 4. 测试（tests-dev）

写差分测试：对每段源码分别用 `Interpreter()` 与 `VirtualMachine()` 执行，
捕获 stdout 与异常文本，断言两者一致（至少覆盖规格开头列出的 11 项差异），
额外覆盖 VM+JIT 模式对同一批源码一致、常量跨赋值、属性 setter、异步/生成器、
嵌套展开、关键字参数顺序、未知运算符不污染栈。
测试文件命名 `tests/test_vm_alignment_*.py`，不要修改既有测试文件。
若产品代码尚未落地导致失败，先保留断言并在完成报告中列出失败项，不要自行修改产品代码。

## 验收（主代理负责）

- AST/VM/VM+JIT 三模式对差分探针全部一致（除错误行列等已知格式差异）。
- 全量 pytest 不低于基线 `2827 passed / 2 skipped / 1 xfailed / 1 xpassed`。
- `ruff check` 改动文件无致命项（F821/E9）。
- 更新 `文档/20-项目整体进度.md` 与交付报告；提交与否按用户指示。
