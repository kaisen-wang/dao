"""
面向对象核心类型
===============

DaoClass（类型）、DaoInstance（实例）、BoundMethod（绑定方法）、SuperProxy（父类代理）。
这些类型由解释器在运行时创建和管理，支撑"道"语言的 OOP 特性。
"""

from ..errors import 道错误
from .callables import DaoCallable, DaoFunction


class DaoError(道错误):
    """道语言自定义错误基类，供用户定义的异常类型继承"""

    def __init__(self, message: str = "发生错误", error_type: str = "DaoError"):
        super().__init__(message, 0, 0, "")
        self.类型 = error_type

    def __str__(self) -> str:
        error_type_name = (
            self.类型.name if hasattr(self.类型, "name") else str(self.类型)
        )
        return f"{error_type_name}: {self.message}"


class DaoTrait:
    """道语言特征 (trait)"""

    def __init__(
        self,
        name: str,
        methods: dict[str, DaoFunction],
        static_methods: dict[str, DaoFunction] | None = None,
    ):
        self.name = name
        self.methods = methods
        self.static_methods = static_methods or {}


class DaoClass(DaoCallable):
    """道语言类型 (class)"""

    def __init__(
        self,
        name: str,
        parent: "DaoClass | None",
        methods: dict[str, DaoFunction],
        static_methods: dict[str, DaoFunction] | None = None,
        private_names: set[str] | None = None,
        implemented_traits: list[DaoTrait] | None = None,
        is_abstract: bool = False,
        abstract_methods: set[str] | None = None,
    ):
        self.name = name
        self.parent = parent
        self.methods = methods
        self.static_methods = static_methods or {}
        self.private_names = private_names or set()
        self.implemented_traits = implemented_traits or []
        self.is_abstract = is_abstract
        self.abstract_methods = abstract_methods or set()

    def find_method(self, name: str) -> DaoFunction | None:
        """查找方法（首先在类中查找，然后在实现的特征中查找，最后沿继承链向上搜索）"""
        if name in self.methods:
            return self.methods[name]
        # 在实现的特征中查找
        for trait in self.implemented_traits:
            if name in trait.methods:
                return trait.methods[name]
        # 沿继承链向上搜索
        if self.parent and isinstance(self.parent, DaoClass):
            return self.parent.find_method(name)
        return None

    def find_static_method(self, name: str) -> DaoFunction | None:
        """查找静态方法（首先在类中查找，然后在实现的特征中查找，最后沿继承链向上搜索）"""
        if name in self.static_methods:
            return self.static_methods[name]
        # 在实现的特征中查找
        for trait in self.implemented_traits:
            if name in trait.static_methods:
                return trait.static_methods[name]
        # 沿继承链向上搜索
        if self.parent:
            return self.parent.find_static_method(name)
        return None

    def arity(self) -> int:
        init = self.find_method("初始化")
        return init.arity() if init else 0

    def call(self, args: list, kwargs: dict) -> object:
        raise NotImplementedError("类型实例化由解释器处理")

    def __repr__(self) -> str:
        return f"<类型 {self.name}>"


class DaoInstance:
    """道语言对象实例"""

    def __init__(self, klass: DaoClass):
        self.klass = klass
        self.fields: dict[str, object] = {}

    def get_field(self, name: str):
        """获取实例字段或绑定方法"""
        if name in self.fields:
            return self.fields[name]
        method = self.klass.find_method(name)
        if method is not None:
            return BoundMethod(self, method)
        return None

    def set_field(self, name: str, value: object):
        """设置实例字段"""
        self.fields[name] = value

    def __repr__(self) -> str:
        return f"<{self.klass.name} 实例>"

    def __eq__(self, other):
        if isinstance(other, DaoInstance):
            return self is other
        return NotImplemented

    def __hash__(self):
        return id(self)


class BoundMethod(DaoCallable):
    """绑定到实例的方法"""

    def __init__(self, instance: DaoInstance, method: DaoFunction):
        self.instance = instance
        self.method = method

    def arity(self) -> int:
        return self.method.arity()

    def call(self, args: list, kwargs: dict) -> object:
        raise NotImplementedError("绑定方法调用由解释器处理")

    def __repr__(self) -> str:
        return f"<方法 {self.instance.klass.name}.{self.method.name}>"


class SuperProxy:
    """父对象代理，用于通过父类调用方法"""

    def __init__(self, instance: DaoInstance, parent_class: DaoClass):
        self.instance = instance
        self.parent_class = parent_class


class DaoGenerator:
    """生成器对象（预生成所有值的简化实现）"""

    def __init__(self, func, args: list, kwargs: dict, interpreter):
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.interpreter = interpreter
        self._values = self._collect_all_values()
        self._index = 0

    def _collect_all_values(self):
        """收集所有产出的值"""
        from ..errors import 产出信号, 返回信号

        values = []

        def bind_params(func_env):
            for i, param in enumerate(self.func.params):
                if i < len(self.args):
                    func_env.define(param, self.args[i])
                elif param in self.kwargs:
                    func_env.define(param, self.kwargs[param])
                elif param in self.func.default_values:
                    func_env.define(param, self.func.default_values[param])
                else:
                    from ..errors import 运行时错误

                    raise 运行时错误(f"函数 '{self.func.name}' 缺少参数 '{param}'")

        func_env = self.func.closure_env.create_child()
        bind_params(func_env)

        def exec_block_with_yield(statements, env, values):
            from ..errors import 继续信号, 跳出信号

            for stmt in statements:
                try:
                    stmt_name = stmt.__class__.__name__

                    if stmt_name == "WhileStmt":
                        while self.interpreter._is_truthy(
                            self.interpreter.eval_expression(stmt.condition, env)
                        ):
                            try:
                                for s in stmt.body:
                                    for s in [s]:
                                        exec_block_with_yield([s], env, values)
                            except 跳出信号:
                                break
                            except 继续信号:
                                continue

                    elif stmt_name == "ForInStmt":
                        iterable = self.interpreter.eval_expression(stmt.iterable, env)
                        if not hasattr(iterable, "__iter__"):
                            from ..errors import 类型错误

                            raise 类型错误(f"类型 '{type(iterable).__name__}' 不可遍历")
                        for item in iterable:
                            try:
                                env.values[stmt.variable] = item
                                for s in stmt.body:
                                    exec_block_with_yield([s], env, values)
                            except 跳出信号:
                                break
                            except 继续信号:
                                continue

                    elif stmt_name == "ForRangeStmt":
                        start = self.interpreter.eval_expression(stmt.start, env)
                        end = self.interpreter.eval_expression(stmt.end, env)
                        step = (
                            self.interpreter.eval_expression(stmt.step, env)
                            if stmt.step
                            else 1
                        )

                        current = start
                        while current <= end:
                            try:
                                env.values[stmt.variable] = current
                                for s in stmt.body:
                                    exec_block_with_yield([s], env, values)
                                current += step
                            except 跳出信号:
                                break
                            except 继续信号:
                                current += step
                                continue

                    else:
                        self.interpreter.exec_statement(stmt, env)

                except 产出信号 as e:
                    values.append(e.value)
                except 跳出信号:
                    raise
                except 继续信号:
                    raise
                except 返回信号:
                    raise

        try:
            exec_block_with_yield(self.func.body, func_env, values)
        except 返回信号:
            pass

        return values

    def __iter__(self):
        """返回迭代器"""
        return self

    def __next__(self):
        """获取下一个值"""
        if self._index >= len(self._values):
            raise StopIteration
        value = self._values[self._index]
        self._index += 1
        return value

    def __repr__(self) -> str:
        return f"<生成器>"
