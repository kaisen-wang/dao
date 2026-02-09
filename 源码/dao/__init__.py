"""
道（Dao）编程语言解释器
======================

一门基于简体中文的多范式编程语言。

模块结构：
- tokens    : 词元（Token）类型定义
- lexer     : 词法分析器 —— 源代码 → Token流
- ast_nodes : 抽象语法树（AST）节点定义
- parser    : 语法分析器 —— Token流 → AST
- interpreter: 树遍历解释器 —— AST → 执行结果
- environment: 变量作用域与环境管理
- errors    : 统一错误类型
- builtins  : 内置函数（打印、长度等）
"""

__version__ = "0.1.0"
__author__ = "道语言项目组"
