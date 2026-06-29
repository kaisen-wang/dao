```
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.
```

## 道（Dao）编程语言 - 中文多范式编程语言

### 📋 项目概述
道是一门基于简体中文的现代高级编程语言，融合了面向对象、函数式、逻辑编程和元编程四大范式，编译至字节码运行，具有动态类型、管道驱动等特性。

### 🚀 常用命令

#### 安装依赖
```bash
cd 源码
pip install -r requirements.txt
```

#### 运行程序
```bash
# 启动交互式命令行（REPL）
python main.py

# 执行 .道 文件
python main.py examples/你好世界.道

# 运行所有测试
pytest tests/ -v

# 运行单个测试文件
pytest tests/test_lexer.py -v
```

#### 代码质量
```bash
# 使用 ruff 检查代码
ruff check dao/ tests/
```

### 🏗️ 高级代码架构与结构

#### 整体流程
```
源代码(.道文件)
    ↓ [词法分析 lexer.py]
Token 流
    ↓ [语法分析 parser.py]
抽象语法树 (AST)
    ↓ [树遍历 interpreter.py]
执行结果
```

#### 核心模块架构

```
dao/
├── tokens.py                # 词元类型定义（32个关键字）
├── ast_nodes.py             # AST节点定义（30+节点类型）
├── environment.py           # 词法作用域管理
├── errors.py                # 中文错误类型定义
├── lexer/                   # 词法分析器
│   ├── core.py              # 核心类（初始化+主循环+缩进）
│   └── readers.py           # Token读取（字符串/数值/运算符等）
├── parser/                  # 语法分析器
│   ├── core.py              # 核心类（初始化+基础设施）
│   ├── statements.py        # 语句解析（声明/控制流/OOP等）
│   ├── expressions.py       # 表达式解析（优先级/调用/字面量等）
│   └── modules/             # 模块化解析
│       ├── variable_decl.py      # 变量/常量声明
│       ├── function_decl.py      # 函数/方法/运算符/属性
│       ├── control_flow.py       # if/while/for/break/continue
│       ├── exception_handling.py # try/catch/throw/assert
│       ├── oop_decl.py           # 类/枚举/抽象/特征
│       ├── pattern_matching.py   # 模式匹配
│       ├── module_system.py      # 导入/导出
│       ├── expressions.py        # 表达式/赋值
│       ├── logic_programming.py  # 逻辑编程
│       ├── macros.py             # 宏解析
│       ├── currency_parser.py    # 并发解析器
│       └── currency.py           # 并发语句解析
├── builtins/                # 内置函数
│   ├── callables.py         # 可调用类型基类
│   ├── oop_types.py         # OOP类型（类/实例/方法）
│   ├── functions.py         # 基础内置函数（打印/长度等）
│   └── hof.py               # 高阶函数（映射/筛选/折叠等）
├── interpreter/             # 解释器
│   ├── core.py              # 核心类（组合混入+辅助方法）
│   ├── statements.py        # 语句执行（声明/控制流/OOP等）
│   ├── expressions.py       # 表达式求值（运算/调用/管道等）
│   └── concurrency.py       # 并发编程解释器（异步/协程/通道）
├── logic/                   # 逻辑编程模块
│   ├── core.py              # 核心逻辑引擎
│   ├── solver.py            # 求解器
│   ├── unification.py       # 统一算法
│   ├── backtracking.py      # 回溯搜索
│   ├── exceptions.py        # 逻辑异常
│   └── constraints/         # 约束求解
│       └── core.py          # 约束求解核心
├── macros/                  # 宏系统模块
│   ├── expander.py          # 宏展开器
│   ├── hygiene.py           # 卫生宏处理
│   ├── ast_repr.py          # AST到数据结构转换
│   ├── ast_ops.py           # AST操作工具
│   ├── introspection.py     # AST内省接口
│   ├── scope.py             # 作用域管理
│   ├── registry.py          # 宏注册表
│   ├── pattern_engine.py    # 模式匹配引擎
│   └── exhaustiveness.py    # 穷尽性检查器
└── concurrency/             # 并发编程模块（开发中）
    └── __init__.py
```

#### 关键特性实现位置

- **面向对象编程**：`dao/builtins/oop_types.py` - 类、实例、方法
- **函数式编程**：`dao/builtins/hof.py` - 映射/筛选/折叠等高阶函数
- **逻辑编程**：`dao/logic/` - 事实/规则/查询处理
- **并发编程**：`dao/concurrency/` - 异步/等待、协程/通道
- **异常处理**：`dao/parser/modules/exception_handling.py` - try/except/finally
- **管道操作**：`dao/interpreter/expressions.py` - `|>` 运算符实现

#### 开发状态

| 阶段 | 目标 | 当前状态 |
|------|------|---------|
| Phase 1 | 核心原型：Lexer + Parser + 解释器 + REPL | ✅ 完成 |
| Phase 2 | OOP + FP：类型系统、高阶函数、模式匹配、模块 | ✅ 大部分完成 |
| Phase 3 | 高级特性：逻辑引擎、宏系统、并发 | 🔄 进行中 |
| Phase 4 | 字节码编译 + GraalVM 迁移 + 生态建设 | ⬜ 待开始 |

#### 测试结构
- 词法分析器测试：`tests/test_lexer.py`
- 语法分析器测试：`tests/test_parser.py`
- 解释器测试：`tests/test_interpreter.py`
- 新特性测试：`tests/test_new_features.py`
- 集成测试：`tests/test_integration.py`
- 并发测试：`tests/test_concurrency_parser.py`
- 枚举测试：`tests/test_enum.py`
- 生成器测试：`tests/test_generator.py`
- 特征测试：`tests/test_traits.py`
- 抽象类型测试：`tests/test_abstract_type.py`
- 运算符重载测试：`tests/test_operator_overload.py`
- 属性访问器测试：`tests/test_property_accessor.py`
- 模式匹配测试：`tests/test_pattern_matching.py`
- 解构匹配测试：`tests/test_destructure_matching.py`
- 堆栈跟踪测试：`tests/test_stack_trace.py`
- 宏测试：`tests/test_macros.py`
- 模式匹配宏测试：`tests/test_pattern_macro.py`
- 逻辑编程测试：`tests/logic_programming/`（4个文件）
- 模块系统测试：`tests/module_system/`（4个文件）

### 📚 设计文档位置

详细设计文档存放在 `文档/` 目录下，分为13个章节：
- 01-引言.md
- 02-核心语法.md
- 03-面向对象编程.md
- 04-函数式编程.md
- 05-逻辑编程.md
- 06-元编程.md
- 07-模块系统.md
- 08-并发编程.md
- 09-类型系统与运行时.md
- 10-标准库.md
- 11-关键字总表.md
- 12-综合示例.md
- 13-结论与展望.md

## 注意事项

- 请使用UTF-8编码
- 道语言没有花括号代码块
- 所有用户可见的错误消息必须使用中文
- 保持AST节点的不可变性(frozen=True或避免修改)
- 新增语法特性时需同步更新：tokens.py, ast_nodes.py, lexer/, parser/, interpreter/, tests/
- 测试覆盖率目标：每个新特性至少3个测试用例
- 如果代码文件较大尝试拆分为多个文件或合并到一个目录下
- 开发测试完成后请提交PR
