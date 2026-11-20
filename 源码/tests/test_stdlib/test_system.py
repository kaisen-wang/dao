import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.stdlib.system import (
    _stdlib_取环境变量, _stdlib_设环境变量, _stdlib_命令行参数,
    _stdlib_当前目录, _stdlib_切换目录,
    _stdlib_关键字表, _stdlib_内置函数名, _stdlib_标准库模块名,
    create_module_env,
)
from dao.errors import 运行时错误


class TestSystemEnvVar:
    def test_get_set_env(self):
        _stdlib_设环境变量("DAO_TEST_VAR", "测试值")
        assert _stdlib_取环境变量("DAO_TEST_VAR") == "测试值"

    def test_get_env_not_exist(self):
        try:
            _stdlib_取环境变量("DAO_NONEXISTENT_VAR_XYZ")
            assert False, "应抛出运行时错误"
        except 运行时错误:
            pass

    def test_get_env_default(self):
        assert _stdlib_取环境变量("DAO_NONEXISTENT_VAR_XYZ", "默认") == "默认"


class TestSystemArgs:
    def test_argv(self):
        result = _stdlib_命令行参数()
        assert isinstance(result, list)
        assert len(result) > 0


class TestSystemDir:
    def test_cwd(self):
        result = _stdlib_当前目录()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_chdir_not_exist(self):
        try:
            _stdlib_切换目录("/不存在的目录")
            assert False, "应抛出运行时错误"
        except 运行时错误:
            pass


class TestSystemModuleEnv:
    def test_create_module_env(self):
        env = create_module_env()
        expected = {
            "取环境变量", "设环境变量", "命令行参数", "执行命令",
            "当前目录", "切换目录", "退出", "平台",
            "关键字表", "内置函数名", "标准库模块名",
        }
        assert set(env.exports) == expected
        assert set(env.values) == expected
        assert "平台" in env.values
        assert isinstance(env.values["平台"], str)
        for 名称 in ("关键字表", "内置函数名", "标准库模块名"):
            assert env.values[名称].param_count == 0


class TestSystemMetadata:
    def test_关键字表(self):
        from dao.tokens import KEYWORDS

        assert _stdlib_关键字表() == list(KEYWORDS)
        assert "定义" in _stdlib_关键字表()

    def test_内置函数名(self):
        from dao.builtins.functions import get_builtins
        from dao.builtins.hof import get_interpreter_builtins

        expected = list(get_builtins()) + list(get_interpreter_builtins())
        assert _stdlib_内置函数名() == expected
        assert "诊断源码" in _stdlib_内置函数名()

    def test_标准库模块名(self):
        from dao.stdlib.registry import STDLIB_REGISTRY

        assert _stdlib_标准库模块名() == list(STDLIB_REGISTRY.keys())
        assert "系统" in _stdlib_标准库模块名()