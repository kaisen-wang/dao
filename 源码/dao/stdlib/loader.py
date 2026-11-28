"""道语言标准库模块加载器。

根据模块路径从注册表中取得对应的环境工厂函数并创建模块环境。
"""

from typing import ClassVar

from ..environment import Environment
from .registry import STDLIB_REGISTRY


class StdlibLoader:
    """标准库加载器，判断模块路径并加载对应模块环境。"""

    STDLIB_NAMES = None

    # 直觉别名：提供更符合直觉的写法，原模块名始终保持可用。
    MODULE_ALIASES: ClassVar[dict[str, str]] = {
        "异步": "异步IO",
        "加密": "密码",
    }

    @classmethod
    def _ensure_names(cls):
        """惰性缓存注册表中的标准库模块名集合。"""
        if cls.STDLIB_NAMES is None:
            cls.STDLIB_NAMES = set(STDLIB_REGISTRY.keys())

    @classmethod
    def resolve_module_name(cls, module_path: str) -> str:
        """把模块路径首段的别名解析为注册表中的真实模块名。"""
        parts = module_path.split(".")
        parts[0] = cls.MODULE_ALIASES.get(parts[0], parts[0])
        return ".".join(parts)

    @classmethod
    def is_stdlib_module(cls, module_path: str) -> bool:
        """判断给定模块路径是否属于标准库。"""
        cls._ensure_names()
        module_name = cls.resolve_module_name(module_path).split(".")[0]
        return module_name in cls.STDLIB_NAMES

    @classmethod
    def load(cls, module_path: str, interpreter) -> Environment:
        """加载标准库模块并返回其导出环境。"""
        module_name = cls.resolve_module_name(module_path).split(".")[0]
        create_func = STDLIB_REGISTRY[module_name]
        module_env = create_func(interpreter)
        return module_env
