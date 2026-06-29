import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.stdlib.system import (
    _stdlib_取环境变量, _stdlib_设环境变量, _stdlib_命令行参数,
    _stdlib_当前目录, _stdlib_切换目录,
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
        assert "取环境变量" in env.values
        assert "平台" in env.values
        assert isinstance(env.values["平台"], str)