"""
语法分析器包
===========

将 Token 流转换为抽象语法树（AST）。
按职责拆分为：
- core        : 核心 Parser 类 —— 初始化、基础设施、入口方法
- statements  : 语句解析混入 —— 所有 parse_*_stmt 方法
- expressions : 表达式解析混入 —— 所有表达式优先级解析方法
"""

from .core import Parser

__all__ = ['Parser']
