
_STDLIB_REGISTRY: dict[str, callable] = {}


def register_module(name: str, create_func: callable) -> None:
    _STDLIB_REGISTRY[name] = create_func


def get_registry() -> dict[str, callable]:
    return _STDLIB_REGISTRY.copy()


def _init_registry():
    from . import text, math, collection, time
    from . import encoding, file, system
    from . import test, log, network

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


_initialized = False


def ensure_initialized():
    global _initialized
    if not _initialized:
        _init_registry()
        _initialized = True


class _RegistryProxy:
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