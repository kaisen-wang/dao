"""
环境（作用域）管理
================

实现词法作用域（Lexical Scoping）：
- 每个代码块（函数、循环等）创建一个新的环境
- 子环境可以访问父环境的变量
- 变量赋值只影响当前环境（除非使用显式查找）
"""

from .errors import 名称错误, 运行时错误


class Environment:
    """
    变量环境（作用域）

    属性：
        parent  : 父环境（外层作用域），为None时表示全局作用域
        values  : 当前作用域中的变量名 → 值 的映射
        constants: 记录哪些变量名是常量，不可重新赋值
        call_stack: 调用栈，用于错误追踪
        current_frame: 当前栈帧信息
    """

    def __init__(self, parent: "Environment | None" = None):
        self.parent = parent
        self.values: dict[str, object] = {}
        self.constants: set[str] = set()
        self.call_stack: list[dict] = []
        self.current_frame: dict | None = None

    def define(self, name: str, value: object, is_constant: bool = False) -> None:
        """
        在当前作用域中定义一个新变量

        参数：
            name        : 变量名
            value       : 初始值
            is_constant : 是否为常量
        """
        if name in self.values:
            raise 运行时错误(f"变量 '{name}' 已经被定义过了")
        self.values[name] = value
        if is_constant:
            self.constants.add(name)

    def get(self, name: str) -> object:
        """
        获取变量的值（沿作用域链向上查找）

        参数：
            name : 变量名
        返回：变量的值
        异常：如果变量未定义则抛出 名称错误
        """
        if name in self.values:
            return self.values[name]
        if self.parent is not None:
            return self.parent.get(name)
        raise 名称错误(f"变量 '{name}' 未定义")

    def set(self, name: str, value: object) -> None:
        """
        设置已存在变量的值（沿作用域链向上查找）

        参数：
            name  : 变量名
            value : 新值
        异常：
            - 如果变量未定义则抛出 名称错误
            - 如果变量是常量则抛出 运行时错误
        """
        if name in self.values:
            if name in self.constants:
                raise 运行时错误(f"常量 '{name}' 不能被重新赋值")
            self.values[name] = value
            return
        if self.parent is not None:
            self.parent.set(name, value)
            return
        raise 名称错误(f"变量 '{name}' 未定义，请先使用 '定义' 声明")

    def has(self, name: str) -> bool:
        """检查变量是否存在（包括父作用域）"""
        if name in self.values:
            return True
        if self.parent is not None:
            return self.parent.has(name)
        return False

    def create_child(self) -> "Environment":
        """创建一个子环境（新的作用域）"""
        child = Environment(parent=self)
        child.call_stack = self.call_stack
        child.current_frame = self.current_frame
        return child

    def push_frame(self, function_name: str, file: str = "", line: int = 0) -> None:
        """压入一个新的调用栈帧"""
        frame = {"function": function_name, "file": file, "line": line}
        self.call_stack.append(frame)
        self.current_frame = frame

    def pop_frame(self) -> None:
        """弹出当前调用栈帧"""
        if self.call_stack:
            self.call_stack.pop()
        self.current_frame = self.call_stack[-1] if self.call_stack else None

    def get_stack(self) -> list:
        """获取当前调用栈"""
        return self.call_stack.copy()
