from ..environment import Environment
from .registry import STDLIB_REGISTRY


class StdlibLoader:
    STDLIB_NAMES = None

    @classmethod
    def _ensure_names(cls):
        if cls.STDLIB_NAMES is None:
            cls.STDLIB_NAMES = set(STDLIB_REGISTRY.keys())

    @classmethod
    def is_stdlib_module(cls, module_path: str) -> bool:
        cls._ensure_names()
        module_name = module_path.split(".")[0]
        return module_name in cls.STDLIB_NAMES

    @classmethod
    def load(cls, module_path: str, interpreter) -> Environment:
        module_name = module_path.split(".")[0]
        create_func = STDLIB_REGISTRY[module_name]
        module_env = create_func(interpreter)
        return module_env