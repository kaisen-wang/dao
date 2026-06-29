from .registry import STDLIB_REGISTRY, register_module as register_module, ensure_initialized


def get_stdlib_modules() -> list[str]:
    ensure_initialized()
    return list(STDLIB_REGISTRY.keys())