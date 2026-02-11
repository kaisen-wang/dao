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

    def set_interpreter(self, interpreter):
        """设置解释器引用"""
        self.interpreter = interpreter

    def call(self, args: list, kwargs: dict) -> object:
        return self.func(self.interpreter, *args, **kwargs)

    def arity(self) -> int:
        return self.param_count

    def __repr__(self) -> str:
        return f"<内置函数 {self.name}>"


class DaoFunction(DaoCallable):
    """用户自定义函数"""

    def __init__(
        self,
        name: str,
        params: list[str],
        default_values: dict,
        body: list,
        closure_env,
        is_generator: bool = False,
        is_getter: bool = False,
        is_setter: bool = False,
    ):
        self.name = name
        self.params = params
        self.default_values = default_values
        self.body = body
        self.closure_env = closure_env
        self.is_generator = is_generator  # 是否包含产出语句
        self.is_getter = is_getter  # 是否是属性 getter
        self.is_setter = is_setter  # 是否是属性 setter

    def arity(self) -> int:
        return len(self.params)

    def __repr__(self) -> str:
        return f"<函数 {self.name}>"


class CurriedFunction(DaoCallable):
    """柯里化后的函数"""

    def __init__(self, original: DaoCallable, accumulated_args: list = []):
        self.original = original
        self.accumulated_args = accumulated_args.copy()
        self.interpreter = None

    def call(self, args: list, kwargs: dict) -> object:
        if not args:
            return self
        new_args = self.accumulated_args + args
        expected_arity = self.original.arity()
        if expected_arity == -1:
            return self.original.call(new_args, kwargs)
        if len(new_args) >= expected_arity:
            if isinstance(self.original, DaoFunction) and self.interpreter:
                return self.interpreter._call_dao_function(
                    self.original, new_args[:expected_arity], kwargs, None
                )
            return self.original.call(new_args[:expected_arity], kwargs)
        result = CurriedFunction(self.original, new_args)
        result.interpreter = self.interpreter
        return result

    def arity(self) -> int:
        expected = self.original.arity()
        if expected == -1:
            return -1
        return max(0, expected - len(self.accumulated_args))

    def __repr__(self) -> str:
        return f"<柯里化函数 {getattr(self.original, 'name', '匿名')}>"
