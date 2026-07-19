"""
错误类型定义
==========

定义"道"语言在编译和运行各阶段可能产生的错误类型。
所有错误都包含源代码位置信息，方便用户定位问题。
"""


class 道错误(Exception):
    """所有"道"语言错误的基类"""

    def __init__(
        self,
        message: str,
        line: int = 0,
        column: int = 0,
        source: str = "",
        stack: list | None = None,
        filename: str = "",
    ):
        self.message = message
        self.line = line
        self.column = column
        self.source = source
        self.stack = stack or []
        self.filename = filename
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        file_info = ""
        if self.filename:
            file_info = f"文件: {self.filename}, "
        elif self.source and "\n" not in self.source:
            file_info = f"文件: {self.source}, "
        base_msg = f"[{file_info}行 {self.line}, 列 {self.column}] {self.message}"
        if self.line > 0 and self.source:
            lines = self.source.splitlines()
            if 0 <= self.line - 1 < len(lines):
                line_content = lines[self.line - 1].rstrip()
                base_msg = f"{base_msg}\n{line_content}\n{' ' * (self.column - 1)}{'^'}"

        if self.stack:
            base_msg += "\n\n调用栈:"
            for i, frame in enumerate(self.stack):
                func_name = frame.get("function", "<匿名>")
                src_file = frame.get("file", "<未知>")
                src_line = frame.get("line", "?")
                base_msg += (
                    f"\n  {i}. 在 {func_name}() (文件: {src_file}, 行: {src_line})"
                )

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


class 宏展开错误(道错误):
    """宏展开阶段的错误（如递归深度超限、参数不匹配等）"""

    pass


class 类型别名错误(道错误):
    """类型别名相关错误（如循环引用、重定义等）"""

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


class 错误信息:
    """捕获到的错误信息包装，支持 .信息 .行 .列 .类型 等属性访问和友好的 str() 显示"""

    def __init__(self, 信息="", 类型="", 行=0, 列=0, 文件名="", 来源="", 堆栈=""):
        self.信息 = 信息
        self.类型 = 类型
        self.行 = 行
        self.列 = 列
        self.文件名 = 文件名
        self.来源 = 来源
        self.堆栈 = 堆栈

    def __getitem__(self, key):
        return getattr(self, key)

    def __contains__(self, key):
        return hasattr(self, key)

    def __str__(self):
        msg = f"[{self.类型}] {self.信息}" if self.类型 else str(self.信息)
        if self.行:
            msg += f" (行 {self.行}"
            if self.列:
                msg += f", 列 {self.列}"
            msg += ")"
        if self.文件名:
            msg += f" 文件: {self.文件名}"
        if self.来源 and "\n" not in self.来源:
            msg += f"\n{self.来源}"
        if self.堆栈:
            msg += f"\n\n调用栈:\n{self.堆栈}"
        return msg
