import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.stdlib.loader import StdlibLoader
from dao.stdlib.registry import STDLIB_REGISTRY, ensure_initialized, register_module


class TestStdlibLoader:
    def test_is_stdlib_module_true(self):
        ensure_initialized()
        assert StdlibLoader.is_stdlib_module("文本") is True

    def test_is_stdlib_module_false(self):
        assert StdlibLoader.is_stdlib_module("不存在的模块") is False

    def test_load_module(self):
        ensure_initialized()
        env = StdlibLoader.load("文本", None)
        assert env is not None
        assert "分割" in env.values

    def test_load_module_caching(self):
        ensure_initialized()
        env1 = StdlibLoader.load("数学", None)
        env2 = StdlibLoader.load("数学", None)
        assert env1 is not env2


class TestStdlibRegistry:
    def test_registry_contains_module(self):
        ensure_initialized()
        assert "文本" in STDLIB_REGISTRY
        assert "数学" in STDLIB_REGISTRY

    def test_registry_keys(self):
        ensure_initialized()
        keys = list(STDLIB_REGISTRY.keys())
        assert len(keys) >= 10

    def test_registry_getitem(self):
        ensure_initialized()
        create_func = STDLIB_REGISTRY["文本"]
        assert callable(create_func)