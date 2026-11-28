"""@ 注解的解释器运行语义测试。"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from dao.builtins import DaoFunction
from dao.environment import Environment
from dao.errors import 运行时错误
from dao.interpreter.core import Interpreter
from dao.lexer import Lexer
from dao.parser import Parser


def run(source: str):
    """解析并解释执行一段道语言源码，返回最后一条语句的值。"""
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    interpreter = Interpreter()
    return interpreter.execute(ast)


class _AnnotationStub:
    """轻量注解桩：直接测试解释器逻辑，不依赖解析器。"""

    def __init__(self, name, args=None, kwargs=None):
        self.name = name
        self.args = args or []
        self.kwargs = kwargs or {}
        self.line = 0
        self.column = 0


class _Target:
    """可作为注解目标的普通对象（允许写属性）。"""


class TestApplyAnnotationsDirect:
    """不依赖解析器的直接单元测试。"""

    def test_none_return_keeps_target_and_records_metadata(self):
        env = Environment()
        # 空函数体：调用后返回 None，按语义应保留原目标
        decorator = DaoFunction(
            name="标记",
            params=["fn"],
            default_values={},
            body=[],
            closure_env=env,
        )
        env.define("标记", decorator)

        target = _Target()
        result = Interpreter()._apply_annotations(
            target, [_AnnotationStub("标记")], env
        )
        assert result is target
        assert result.__注解__ == ["标记"]

    def test_undefined_annotation_raises_chinese_error(self):
        env = Environment()
        with pytest.raises(运行时错误, match="注解 '不存在' 未定义"):
            Interpreter()._apply_annotations(
                _Target(), [_AnnotationStub("不存在")], env
            )


class TestInterpreterAnnotation:
    """端到端测试：@ 注解作用于变量 / 函数声明。"""

    def test_log_annotation_wraps_function(self):
        # 日志注解返回一个包装函数；被装饰函数仍可正常调用，并记录调用事件
        source = """定义 事件 = []
函数 日志(fn)
    函数 包装(x)
        事件.追加(x)
        返回 fn(x)
    返回 包装

@日志
函数 加倍(x)
    返回 x * 2

定义 r = 加倍(5)
事件.长度 * 10 + r
"""
        assert run(source) == 20

    def test_replacement_annotation_on_variable(self):
        source = """函数 替换值(v)
    返回 v + 100

@替换值
定义 x = 5
x
"""
        assert run(source) == 105

    def test_replacement_annotation_with_args_and_kwargs(self):
        # 注解参数按 fn(target, *args, **kwargs) 形式传入
        source = """函数 带参(fn, 倍数, 偏移=0)
    返回 函数(x) => fn(x) * 倍数 + 偏移

@带参(3, 偏移=2)
函数 加一(x)
    返回 x + 1

加一(1)
"""
        assert run(source) == 8

    def test_none_return_keeps_original(self):
        source = """函数 不改(v)
    返回 空

@不改
定义 x = 5
x
"""
        assert run(source) == 5

    def test_multiple_annotations_applied_bottom_up(self):
        # 书写顺序 @A @B，应用顺序为 B → A（与 Python 装饰器一致）
        source = """定义 顺序 = []
函数 A(fn)
    顺序.追加("A")
    返回 fn
函数 B(fn)
    顺序.追加("B")
    返回 fn

@A
@B
定义 x = 5
顺序
"""
        assert run(source) == ["B", "A"]

    def test_class_declaration_annotation(self):
        source = """函数 替换类(c)
    返回 "已替换"

@替换类
类型 用户
    定义 名字 = ""

用户
"""
        assert run(source) == "已替换"

    def test_undefined_annotation_raises_chinese_error(self):
        with pytest.raises(运行时错误, match="注解 '不存在' 未定义"):
            run("""@不存在
定义 x = 5
""")

    def test_non_callable_annotation_raises_chinese_error(self):
        with pytest.raises(运行时错误, match="注解 'n' 不可调用"):
            run("""定义 n = 123
@n
定义 x = 5
""")

    def test_trait_and_enum_declaration_annotations(self):
        """注解可附着于 TraitDecl / EnumDecl，并在绑定前完成替换。

        注解函数必须接收被装饰对象作为第一个参数，故参数个数本身也
        验证了 target 已正确传入。
        """
        source = """函数 替换特征(t, 文本)
    返回 文本

@替换特征("已替换特征")
特征 可说话
    函数 说()
        返回 "嗨"

函数 替换枚举(e, 文本)
    返回 文本

@替换枚举("已替换枚举")
枚举 颜色
    红
    绿

定义 a = 可说话
定义 b = 颜色
a + "|" + b
"""
        assert run(source) == "已替换特征|已替换枚举"

    def test_async_function_declaration_annotation(self):
        """注解可附着于 AsyncFunctionDecl，包装后仍可被 等待 调用。"""
        source = """定义 事件 = []
函数 日志(fn)
    函数 包装(x)
        事件.追加(x)
        返回 fn(x)
    返回 包装

@日志
异步 函数 加倍(x)
    返回 x * 2

定义 r = 等待 加倍(5)
事件.长度 * 10 + r
"""
        assert run(source) == 20

    def test_abstract_declaration_annotation(self):
        """AbstractDecl 的注解经 ClassDecl 转换流程在 DaoClass 上生效。"""
        source = """函数 替换抽象(c, 文本)
    返回 文本

@替换抽象("已替换抽象")
抽象 类型 形状
    抽象 面积()

形状
"""
        assert run(source) == "已替换抽象"

    def test_class_body_method_annotation_wraps_method(self):
        """类体方法注解在 DaoFunction 构造后应用，包装后可正常调用。"""
        source = """定义 事件 = []
函数 日志(fn)
    函数 包装(x)
        事件.追加(x)
        返回 fn(x)
    返回 包装

类型 用户
    @日志
    函数 加倍(x)
        返回 x * 2

定义 u = 用户()
定义 r = u.加倍(5)
事件.长度 * 10 + r
"""
        assert run(source) == 20

    def test_class_body_static_method_annotation_replaces_method(self):
        """静态方法同样走类体注解路径，注解返回非 None 时替换方法。"""
        source = """函数 换方法(fn)
    函数 新方法()
        返回 99
    返回 新方法

类型 工具
    @换方法
    静态 函数 数值()
        返回 1

工具.数值()
"""
        assert run(source) == 99
