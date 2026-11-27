"""道语言标准库注册表。

集中登记各标准库模块对应的 create_module_env 工厂函数，
通过惰性初始化避免模块级循环导入。
"""

_STDLIB_REGISTRY: dict[str, callable] = {}


def register_module(name: str, create_func: callable) -> None:
    """登记一个标准库模块及其环境工厂函数。"""
    _STDLIB_REGISTRY[name] = create_func


def get_registry() -> dict[str, callable]:
    """返回注册表的一份浅拷贝。"""
    return _STDLIB_REGISTRY.copy()


def _init_registry():
    """导入并登记全部标准库模块工厂函数。"""
    from . import asyncio as _asyncio_mod
    from . import (
        archive as _archive_mod,
        binary as _binary_mod,
        collection,
        crypto,
        db,
        encoding,
        file,
        i18n as _i18n_mod,
        llm,
        log,
        math,
        network,
        path as _path_mod,
        process as _process_mod,
        schedule,
        system,
        test,
        text,
        time,
    )

    register_module("文本", text.create_module_env)
    register_module("数学", math.create_module_env)
    register_module("集合", collection.create_module_env)
    register_module("时间", time.create_module_env)
    register_module("编码", encoding.create_module_env)
    register_module("文件", file.create_module_env)
    register_module("系统", system.create_module_env)
    register_module("测试", test.create_module_env)
    register_module("日志", log.create_module_env)
    register_module("网络", network.create_module_env)
    register_module("异步IO", _asyncio_mod.create_module_env)
    register_module("密码", crypto.create_module_env)
    register_module("数据库", db.create_module_env)
    register_module("调度", schedule.create_module_env)
    register_module("大模型", llm.create_module_env)
    register_module("路径", _path_mod.create_module_env)
    register_module("进程", _process_mod.create_module_env)
    register_module("归档", _archive_mod.create_module_env)
    register_module("二进制", _binary_mod.create_module_env)
    register_module("国际化", _i18n_mod.create_module_env)


_initialized = False


def ensure_initialized():
    """确保注册表已完成初始化，仅首次调用时执行导入。"""
    global _initialized
    if not _initialized:
        _init_registry()
        _initialized = True


class _RegistryProxy:
    """注册表代理，在访问时惰性触发初始化。"""

    def __contains__(self, key):
        ensure_initialized()
        return key in get_registry()

    def __getitem__(self, key):
        ensure_initialized()
        return get_registry()[key]

    def keys(self):
        ensure_initialized()
        return get_registry().keys()


STDLIB_REGISTRY = _RegistryProxy()
