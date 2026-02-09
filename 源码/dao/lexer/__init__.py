"""
词法分析器包
===========

将"道"源代码字符串转换为Token（词元）序列。
按职责拆分为：
- core    : 核心 Lexer 类 —— 初始化、主循环 tokenize()、缩进处理
- readers : Token 读取混入 —— 字符串、数值、标识符、运算符等具体读取方法
"""

from .core import Lexer

__all__ = ['Lexer']
