"""
宏系统模块
==========

道语言的宏系统提供强大的元编程能力，允许开发者在编译期扩展语言的语法。
宏系统支持：

1. 定义宏：使用 '定义宏' 关键字定义宏
2. 引述块：使用 '引述' 关键字包裹要操作的代码
3. 注入表达式：使用 '注入' 关键字在引述块中注入表达式
4. 宏调用：使用 '!' 前缀调用宏

核心功能：
- 编译期宏执行
- 卫生宏处理（防止变量捕获）
- 递归宏展开
- 高级错误恢复

模块结构：
- expander.py：宏展开器
- hygiene.py：卫生宏处理
- ast_repr.py：AST到数据结构的转换
- ast_ops.py：AST操作工具
- introspection.py：AST内省接口
- scope.py：作用域管理
- registry.py：宏注册表
"""

from .ast_ops import ASTOperations
from .ast_repr import ASTToData, DataToAST
from .expander import MacroExpander
from .hygiene import HygieneProcessor
from .introspection import ASTIntrospector
from .registry import MacroRegistry
from .scope import MacroScope

__all__ = [
    "MacroExpander",
    "MacroRegistry",
    "MacroScope",
    "HygieneProcessor",
    "ASTToData",
    "DataToAST",
    "ASTOperations",
    "ASTIntrospector",
]
