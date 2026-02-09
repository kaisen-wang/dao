"""
面向对象核心类型
===============

DaoClass（类型）、DaoInstance（实例）、BoundMethod（绑定方法）、SuperProxy（父类代理）。
这些类型由解释器在运行时创建和管理，支撑"道"语言的 OOP 特性。
"""

from .callables import DaoCallable, DaoFunction


class DaoClass(DaoCallable):
    """道语言类型 (class)"""

    def __init__(self, name: str, parent: "DaoClass | None",
                 methods: dict[str, DaoFunction],
                 static_methods: dict[str, DaoFunction] | None = None,
                 private_names: set[str] | None = None):
        self.name = name
        self.parent = parent
        self.methods = methods
        self.static_methods = static_methods or {}
        self.private_names = private_names or set()

    def find_method(self, name: str) -> DaoFunction | None:
        """查找方法（沿继承链向上搜索）"""
        if name in self.methods:
            return self.methods[name]
        if self.parent:
            return self.parent.find_method(name)
        return None

    def find_static_method(self, name: str) -> DaoFunction | None:
        """查找静态方法（沿继承链向上搜索）"""
        if name in self.static_methods:
            return self.static_methods[name]
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
