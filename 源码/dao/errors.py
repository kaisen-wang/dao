"""
错误类型定义
==========

定义"道"语言在编译和运行各阶段可能产生的错误类型。
所有错误都包含源代码位置信息，方便用户定位问题。
"""


class 道错误(Exception):
    """所有"道"语言错误的基类"""

    def __init__(self, message: str, line: int = 0, column: int = 0, source: str = ""):
        self.message = message
        self.line = line
        self.column = column
        self.source = source
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        base_msg = f"[行 {self.line}, 列 {self.column}] {self.message}"
        if self.line > 0 and self.source:
            lines = self.source.splitlines()
            if 0 <= self.line - 1 < len(lines):
                line_content = lines[self.line - 1].rstrip()
                base_msg = f"{base_msg}\n{line_content}\n{' ' * (self.column - 1)}{'^'}"
        return base_msg


class 词法错误(道错误):
    """词法分析阶段的错误（如非法字符、未闭合的字符串等）"""
    pass


class 语法错误(道错误):
    """语法分析阶段的错误（如缺少括号、非法表达式等）"""
    pass


class 运行时错误(道错误):
    """运行时错误（如类型不匹配、除零、未定义变量等）"""
    pass


class 类型错误(运行时错误):
    """类型不匹配错误"""
    pass


class 名称错误(运行时错误):
    """变量未定义错误"""
    pass


class 索引错误(运行时错误):
    """索引越界错误"""
    pass


class 断言失败(运行时错误):
    """断言失败"""
    pass


class 跳出信号(Exception):
    """跳出循环的控制流信号（非真正的错误）"""
    pass


class 继续信号(Exception):
    """继续循环的控制流信号（非真正的错误）"""
    pass


class 返回信号(Exception):
    """函数返回的控制流信号（非真正的错误）"""

    def __init__(self, value):
        self.value = value
        super().__init__()


class 产出信号(Exception):
    """生成器产出值的控制流信号（非真正的错误）"""

    def __init__(self, value):
        self.value = value
        super().__init__()
