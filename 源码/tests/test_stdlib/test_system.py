import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from dao.stdlib.system import (
    _stdlib_取环境变量, _stdlib_设环境变量, _stdlib_命令行参数,
    _stdlib_当前目录, _stdlib_切换目录,
    _stdlib_关键字表, _stdlib_内置函数名, _stdlib_标准库模块名,
    _stdlib_解析参数, _stdlib_生成帮助文本,
    create_module_env,
)
from dao.errors import 类型错误, 运行时错误


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


class TestSystemArgsParse:
    """argv 解析：短/长选项、开关、类型转换、位置参数与帮助文本。"""

    def _选项(self):
        return [
            {"名称": "输出", "短": "o", "长": "output", "类型": "文本", "默认": "out.txt", "说明": "输出路径"},
            {"名称": "详细", "短": "v", "长": "verbose", "类型": "开关", "说明": "详细模式"},
            {"名称": "次数", "长": "count", "类型": "整数", "默认": 1, "说明": "执行次数"},
        ]

    def test_解析短长选项与位置参数(self):
        结果 = _stdlib_解析参数(["文件.txt", "-o", "a.txt", "-v", "--count=3", "额外"], self._选项())
        assert 结果["帮助"] is False
        assert 结果["位置参数"] == ["文件.txt", "额外"]
        assert 结果["选项"] == {"输出": "a.txt", "详细": True, "次数": 3}

    def test_长选项等号与开关假值(self):
        结果 = _stdlib_解析参数(["--output=b.txt", "--verbose=false"], self._选项())
        assert 结果["选项"]["输出"] == "b.txt"
        assert 结果["选项"]["详细"] is False

    def test_短选项粘连取值(self):
        结果 = _stdlib_解析参数(["-oa.txt"], self._选项())
        assert 结果["选项"]["输出"] == "a.txt"

    def test_分隔符之后均为位置参数(self):
        结果 = _stdlib_解析参数(["--", "-o", "值"], self._选项())
        assert 结果["位置参数"] == ["-o", "值"]

    def test_帮助标记优先(self):
        assert _stdlib_解析参数(["--help", "--未知"], self._选项())["帮助"] is True
        assert _stdlib_解析参数(["-h"], self._选项())["帮助"] is True

    def test_未知选项(self):
        with pytest.raises(运行时错误):
            _stdlib_解析参数(["--未知"], self._选项())
        with pytest.raises(运行时错误):
            _stdlib_解析参数(["-x"], self._选项())

    def test_缺少取值(self):
        with pytest.raises(运行时错误):
            _stdlib_解析参数(["--output"], self._选项())
        with pytest.raises(运行时错误):
            _stdlib_解析参数(["-o"], self._选项())

    def test_类型转换失败(self):
        with pytest.raises(运行时错误):
            _stdlib_解析参数(["--count", "不是整数"], self._选项())
        with pytest.raises(运行时错误):
            _stdlib_解析参数(["--verbose=maybe"], self._选项())

    def test_必填选项与重复定义(self):
        with pytest.raises(运行时错误):
            _stdlib_解析参数([], [{"名称": "源", "长": "src", "必填": True}])
        with pytest.raises(运行时错误):
            _stdlib_解析参数([], [
                {"名称": "甲", "长": "same"},
                {"名称": "乙", "长": "same"},
            ])

    def test_选项定义格式错误(self):
        with pytest.raises(类型错误):
            _stdlib_解析参数([], 123)
        with pytest.raises(运行时错误):
            _stdlib_解析参数([], [{"名称": "无选项"}])
        with pytest.raises(运行时错误):
            _stdlib_解析参数([], [{"名称": "甲", "短": "ab"}])

    def test_生成帮助文本(self):
        文本 = _stdlib_生成帮助文本("应用", self._选项(), "示例程序")
        assert "用法: 应用" in 文本
        assert "示例程序" in 文本
        assert "-o, --output" in 文本
        assert "输出路径" in 文本
        assert "--help" in 文本
        with pytest.raises(类型错误):
            _stdlib_生成帮助文本("")


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
            "取环境变量", "设环境变量", "命令行参数", "解析参数",
            "生成帮助文本", "执行命令", "当前目录", "切换目录",
            "退出", "平台",
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