"""
可调用对象体系
=============

定义"道"语言中所有可调用对象的基类和实现：
- DaoCallable       : 可调用对象基类
- BuiltinFunction   : 纯 Python 内置函数包装
- InterpreterBuiltin: 需要解释器引用的内置函数（高阶函数等）
- DaoFunction       : 用户自定义函数（支持闭包）
"""


class DaoCallable:
    """可调用对象的基类"""

    def call(self, args: list, kwargs: dict) -> object:
        raise NotImplementedError

    def arity(self) -> int:
        """返回参数个数，-1 表示可变参数"""
        return -1


class BuiltinFunction(DaoCallable):
    """内置函数包装器（纯 Python 函数）"""

    def __init__(self, name: str, func, param_count: int = -1):
        self.name = name
        self.func = func
        self.param_count = param_count

    def call(self, args: list, kwargs: dict) -> object:
        return self.func(*args, **kwargs)

    def arity(self) -> int:
        return self.param_count

    def __repr__(self) -> str:
        return f"<内置函数 {self.name}>"


class InterpreterBuiltin(DaoCallable):
    """需要解释器引用的内置函数（用于高阶函数等）"""

    def __init__(self, name: str, func, param_count: int = -1):
        self.name = name
        self.func = func
        self.param_count = param_count
        self.interpreter = None  # 由 Interpreter.__init__ 设置

    def call(self, args: list, kwargs: dict) -> object:
        return self.func(self.interpreter, *args, **kwargs)

    def arity(self) -> int:
        return self.param_count

    def __repr__(self) -> str:
        return f"<内置函数 {self.name}>"


class DaoFunction(DaoCallable):
    """用户自定义函数"""

    def __init__(self, name: str, params: list[str], default_values: dict,
                 body: list, closure_env):
        self.name = name
        self.params = params
        self.default_values = default_values
        self.body = body
        self.closure_env = closure_env

    def arity(self) -> int:
        return len(self.params)

    def __repr__(self) -> str:
        return f"<函数 {self.name}>"
