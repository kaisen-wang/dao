"""道语言标准库模块加载器。

根据模块路径从注册表中取得对应的环境工厂函数并创建模块环境。
"""

from ..environment import Environment
from .registry import STDLIB_REGISTRY


class StdlibLoader:
    """标准库加载器，判断模块路径并加载对应模块环境。"""

    STDLIB_NAMES = None

    @classmethod
    def _ensure_names(cls):
        """惰性缓存注册表中的标准库模块名集合。"""
        if cls.STDLIB_NAMES is None:
            cls.STDLIB_NAMES = set(STDLIB_REGISTRY.keys())

    @classmethod
    def is_stdlib_module(cls, module_path: str) -> bool:
        """判断给定模块路径是否属于标准库。"""
        cls._ensure_names()
        module_name = module_path.split(".")[0]
        return module_name in cls.STDLIB_NAMES

    @classmethod
    def load(cls, module_path: str, interpreter) -> Environment:
        """加载标准库模块并返回其导出环境。"""
        module_name = module_path.split(".")[0]
        create_func = STDLIB_REGISTRY[module_name]
        module_env = create_func(interpreter)
        return module_env
