# 道（Dao）— 多范式中文编程语言

> 一门基于简体中文的、融合四大编程范式的现代高级编程语言

## 🎯 项目简介

"道"是一种全新的通用编程语言，专为中文使用者设计。它的目标不仅是降低编程门槛，更是探索如何将面向对象、函数式、逻辑编程和元编程四大范式优雅地融合在统一的中文语法框架下。

**核心特性：**
- 🇨🇳 **中文原生** — 所有关键字使用简体中文，语法贴合中文表达习惯
- 🔀 **四范式融合** — OOP + FP + 逻辑编程 + 元编程，各司其职、无缝协作
- ⚡ **动态类型** — 灵活高效，可选类型注解满足大型项目需求
- 📦 **字节码运行** — 编译至中间字节码，跨平台 + JIT 高性能
- 🧩 **管道驱动** — `|>` 运算符让数据流动像流水线一样清晰

## 🚀 快速开始

### 从源码运行

```bash
# 进入源码目录
cd 源码

# 安装依赖（需要 Python 3.10+）
pip install -r requirements.txt

# 启动交互式命令行（REPL）
python main.py

# 执行 .道 文件
python main.py examples/你好世界.道

# 使用字节码虚拟机模式执行
python main.py --mode vm examples/你好世界.道

# 运行测试
pytest tests/ -v
```

### 使用 Nuitka 打包为原生可执行文件

```bash
# 安装 Nuitka 及依赖
pip install nuitka ordered-set zstandard patchelf

# 打包为单文件可执行程序
cd 源码
python -m nuitka --onefile --standalone \
    --enable-plugin=no-qt \
    --include-package=dao \
    --output-filename=道 \
    --output-dir=../dist \
    --assume-yes-for-downloads \
    main.py

# 运行打包后的可执行文件
../dist/道                    # 启动 REPL
../dist/道 examples/你好世界.道  # 执行文件
```

**REPL 示例：**
```
道 > 打印("你好，世界！")
你好，世界！

道 > 定义 x = 42
道 > 打印(x * 2)
84

道 > 函数 加法(甲, 乙)
...     返回 甲 + 乙
...
道 > 打印(加法(3, 4))
7
```

## 🔑 语法速览

```
// 变量与函数
定义 名字 = "张三"
常量 版本 = "1.0"

函数 打招呼(名字)
    返回 `你好，{名字}！`

// 面向对象
类型 动物
    初始化(名字)
        本对象.名字 = 名字
    函数 说话()
        打印(`我是{本对象.名字}`)

// 函数式管道
定义 结果 = [1, 2, 3, 4, 5]
    |> 筛选(_ > 2)
    |> 映射(_ * 10)
    // => [30, 40, 50]

// 逻辑编程
逻辑 知识库
    事实: 朋友("甲", "乙")
    规则: 间接朋友(?a, ?c) 如果
        朋友(?a, ?b) 并且 朋友(?b, ?c)

// 异步并发
异步 函数 获取数据()
    定义 结果 = 等待 网络.请求("/api/data")
    返回 结果
```

## 📚 设计文档

设计文档存放在 `文档/` 目录下，按主题分为 13 个章节：

| # | 文件 | 内容 |
|---|------|------|
| 1 | [引言](文档/01-引言.md) | 背景动机、设计目标、报告结构 |
| 2 | [核心语法](文档/02-核心语法.md) | 注释、变量、数据类型、字符串插值、解构、控制流、函数、错误处理、运算符 |
| 3 | [面向对象编程](文档/03-面向对象编程.md) | 类型、继承、特征、抽象类型、静态方法、运算符重载、属性访问器 |
| 4 | [函数式编程](文档/04-函数式编程.md) | 高阶函数、管道运算符、柯里化、函数组合、模式匹配、惰性求值 |
| 5 | [逻辑编程](文档/05-逻辑编程.md) | 事实/规则/查询、否定、约束、剪枝、动态事实 |
| 6 | [元编程](文档/06-元编程.md) | 宏定义、引述/注入、实用宏、AST内省、卫生宏 |
| 7 | [模块系统](文档/07-模块系统.md) | 导入/导出、包管理、条件导入 |
| 8 | [并发编程](文档/08-并发编程.md) | 异步/等待、协程/通道、选择器、并发安全 |
| 9 | [类型系统与运行时](文档/09-类型系统与运行时.md) | 动态类型、可选注解、字节码编译、VM平台评估 |
| 10 | [标准库](文档/10-标准库.md) | 文本、数学、文件、网络、时间、编码、测试等核心模块 |
| 11 | [关键字总表](文档/11-关键字总表.md) | 全部约75个关键字分类速查表 |
| 12 | [综合示例](文档/12-综合示例.md) | 博客推荐系统 — 四范式协作实战 |
| 13 | [结论与展望](文档/13-结论与展望.md) | 总结、挑战、实施路线图 |

> 📄 原始的完整研究报告保存在 [文档.md](文档.md)  
> 📋 详细开发计划见 [开发计划.md](开发计划.md)

## 🗺️ 开发路线图

| 阶段 | 目标 | 当前状态 |
|------|------|---------|
| **Phase 1** | 核心原型：Lexer + Parser + 解释器 + REPL | ✅ 完成 |
| **Phase 2** | OOP + FP：类型系统、高阶函数、模式匹配、模块 | ✅ 大部分完成 |
| **Phase 3** | 高级特性：逻辑引擎、宏系统、并发 | 🔧 已实现核心功能 |
| **Phase 4** | 字节码编译 + VM + JIT + 标准库 + 包管理 | 🔧 已实现核心功能 |

## 📁 项目结构

```
道/
├── readme.md               ← 你正在读的文件
├── 文档.md                 ← 原始完整研究报告
├── 开发计划.md             ← 详细开发计划与任务清单
├── 文档/                   ← 分章节设计文档（13章）
│   ├── 01-引言.md
│   ├── 02-核心语法.md
│   ├── 03-面向对象编程.md
│   ├── 04-函数式编程.md
│   ├── 05-逻辑编程.md
│   ├── 06-元编程.md
│   ├── 07-模块系统.md
│   ├── 08-并发编程.md
│   ├── 09-类型系统与运行时.md
│   ├── 10-标准库.md
│   ├── 11-关键字总表.md
│   ├── 12-综合示例.md
│   └── 13-结论与展望.md
├── dist/                   ← Nuitka 打包输出
│   └── 道                  ← 原生可执行文件（~8.5MB）
└── 源码/                   ← 解释器源代码（Python 3.10+）
    ├── main.py             ← 主入口（REPL + 文件执行）
    ├── requirements.txt    ← Python 依赖
    ├── dao/                ← 核心解释器包
    │   ├── __init__.py        ← 包初始化（版本 0.1.0）
    │   ├── tokens.py          ← 词元类型定义（32个关键字）
    │   ├── ast_nodes.py       ← AST 节点定义（30+节点类型）
    │   ├── environment.py     ← 词法作用域管理
    │   ├── errors.py          ← 中文错误类型
    │   ├── lexer/             ← 词法分析器包
    │   │   ├── core.py           ← 核心类（初始化+主循环+缩进）
    │   │   └── readers.py        ← Token读取（字符串/数值/运算符等）
    │   ├── parser/            ← 语法分析器包
    │   │   ├── core.py           ← 核心类（初始化+基础设施）
    │   │   ├── statements.py     ← 语句解析（声明/控制流/OOP等）
    │   │   ├── expressions.py    ← 表达式解析（优先级/调用/字面量等）
    │   │   └── modules/          ← 解析子模块
    │   │       ├── control_flow.py   ← 控制流解析
    │   │       ├── oop_decl.py       ← OOP 声明解析
    │   │       ├── function_decl.py  ← 函数声明解析
    │   │       ├── pattern_matching.py ← 模式匹配解析
    │   │       ├── logic_programming.py ← 逻辑编程解析
    │   │       ├── macros.py         ← 宏解析
    │   │       ├── module_system.py  ← 模块系统解析
    │   │       └── ...               ← 其他解析子模块
    │   ├── builtins/          ← 内置函数包
    │   │   ├── callables.py      ← 可调用类型基类
    │   │   ├── oop_types.py      ← OOP 类型（类/实例/方法）
    │   │   ├── functions.py      ← 基础内置函数（打印/长度等）
    │   │   └── hof.py            ← 高阶函数（映射/筛选/折叠等）
    │   ├── interpreter/       ← 解释器包
    │   │   ├── core.py           ← 核心类（组合混入+辅助方法）
    │   │   ├── statements.py     ← 语句执行（声明/控制流/OOP等）
    │   │   ├── expressions.py    ← 表达式求值（运算/调用/管道等）
    │   │   └── concurrency.py    ← 并发语句执行
    │   ├── logic/             ← 逻辑编程引擎
    │   │   ├── core.py           ← 知识库核心
    │   │   ├── solver.py         ← 查询求解器
    │   │   ├── unification.py    ← 合一算法
    │   │   ├── backtracking.py   ← 回溯搜索
    │   │   ├── exceptions.py     ← 逻辑编程异常
    │   │   └── constraints/      ← 约束求解子模块
    │   ├── macros/            ← 宏系统
    │   │   ├── expander.py       ← 宏展开器
    │   │   ├── hygiene.py        ← 卫生宏处理
    │   │   ├── introspection.py  ← AST 内省
    │   │   ├── ast_ops.py        ← AST 操作工具
    │   │   ├── ast_repr.py       ← AST 数据表示
    │   │   ├── exhaustiveness.py ← 穷尽性检查
    │   │   ├── pattern_engine.py ← 模式引擎
    │   │   ├── registry.py       ← 宏注册表
    │   │   └── scope.py          ← 作用域管理
    │   ├── concurrency/       ← 并发编程
    │   │   └── __init__.py       ← Channel/Mutex/原子类型
    │   ├── bytecode/          ← 字节码编译
    │   │   ├── opcodes.py        ← 操作码定义
    │   │   ├── code_object.py    ← 代码对象
    │   │   ├── compiler.py       ← 字节码编译器
    │   │   ├── disassembler.py   ← 反汇编器
    │   │   └── frame.py          ← 栈帧
    │   ├── vm/                ← 虚拟机
    │   │   └── core.py           ← VM 核心
    │   ├── jit/               ← JIT 编译
    │   │   ├── compiler.py       ← JIT 编译器
    │   │   ├── hotspot.py        ← 热点检测
    │   │   └── type_feedback.py  ← 类型反馈
    │   ├── types/             ← 类型系统
    │   │   ├── checker.py        ← 类型检查器
    │   │   ├── core.py           ← 类型核心
    │   │   └── alias_registry.py ← 类型别名注册
    │   ├── package/           ← 包管理
    │   │   ├── config.py         ← 包配置
    │   │   ├── manager.py        ← 包管理器
    │   │   ├── resolver.py       ← 依赖解析
    │   │   └── version.py        ← 版本管理
    │   └── stdlib/            ← 标准库
    │       ├── loader.py         ← 模块加载器
    │       ├── registry.py       ← 模块注册表
    │       ├── text.py           ← 文本处理
    │       ├── math.py           ← 数学运算
    │       ├── file.py           ← 文件操作
    │       ├── network.py        ← 网络请求
    │       ├── time.py           ← 时间日期
    │       ├── encoding.py       ← 编码转换
    │       ├── collection.py     ← 集合工具
    │       ├── system.py         ← 系统信息
    │       ├── log.py            ← 日志模块
    │       └── test.py           ← 测试框架
    ├── tests/              ← 测试套件（65个测试文件，180+测试用例）
    │   ├── test_lexer.py          ← 词法分析器测试
    │   ├── test_parser.py         ← 语法分析器测试
    │   ├── test_interpreter.py    ← 解释器测试
    │   ├── test_integration.py    ← 集成测试
    │   ├── test_bytecode_*.py     ← 字节码编译测试
    │   ├── test_vm.py             ← 虚拟机测试
    │   ├── test_jit.py            ← JIT 测试
    │   ├── test_logic_*.py        ← 逻辑编程测试
    │   ├── test_macros.py         ← 宏系统测试
    │   ├── test_traits.py         ← 特征测试
    │   ├── test_pattern_matching.py ← 模式匹配测试
    │   ├── test_type_*.py         ← 类型系统测试
    │   ├── test_stdlib/           ← 标准库测试
    │   ├── logic_programming/     ← 逻辑编程专项测试
    │   └── module_system/         ← 模块系统专项测试
    └── examples/           ← 示例程序（46个 .道 文件）
        ├── 你好世界.道
        ├── 基础示例.道
        ├── 斐波那契.道
        ├── 面向对象.道
        ├── 高阶函数.道
        ├── 模式匹配.道
        ├── 宏系统示例.道
        ├── 枚举示例.道
        ├── 综合示例.道
        ├── concurrency_tests/  ← 并发编程示例
        ├── logic_programming/  ← 逻辑编程示例
        └── ...
```

## 🛠️ 技术架构

```
源代码(.道文件)
    ↓ [词法分析 lexer/]
Token 流
    ↓ [语法分析 parser/]
抽象语法树 (AST)
    ↓
    ├── [树遍历 interpreter/]  ← 解释器模式（默认）
    │       ↓
    │   执行结果
    │
    └── [字节码编译 bytecode/]  ← VM 模式（--mode vm）
            ↓
        字节码 (CodeObject)
            ↓ [虚拟机 vm/]
            ↓ [JIT 编译 jit/]  ← 可选（--jit）
            ↓
        执行结果
```

**双执行模式：**
- **解释器模式**（默认）：AST 树遍历，启动快，适合交互式开发
- **VM 模式**（`--mode vm`）：编译至字节码后由虚拟机执行，支持 JIT 热点优化

**打包部署：** 通过 Nuitka 编译为原生可执行文件，无需 Python 环境即可运行
