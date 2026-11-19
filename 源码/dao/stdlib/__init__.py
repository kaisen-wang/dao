"""道语言标准库包，统一导出注册表与模块查询入口。"""

from .registry import STDLIB_REGISTRY, register_module as register_module, ensure_initialized


def get_stdlib_modules() -> list[str]:
    """返回所有已登记的标准库模块名列表。"""
    ensure_initialized()
    return list(STDLIB_REGISTRY.keys())
