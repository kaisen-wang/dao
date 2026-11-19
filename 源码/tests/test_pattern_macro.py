"""
模式匹配宏测试模块
测试道语言的模式匹配宏功能
"""

import os
import sys

import pytest

# 确保能导入dao包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dao.errors import 返回信号, 道错误
from dao.interpreter import Interpreter
from dao.lexer import Lexer
from dao.parser import Parser


def run_code(source: str, filename: str = "<测试>") -> tuple[object, Interpreter]:
    """执行一段道语言代码，返回结果和解释器实例"""
    from dao.macros.registry import MacroRegistry

    # 清理宏注册表，避免测试间干扰
    MacroRegistry().clear()

    interpreter = Interpreter()

    # 1. 词法分析
    lexer = Lexer(source, filename)
    tokens = lexer.tokenize()

    # 2. 语法分析
    parser = Parser(tokens, source)
    ast = parser.parse()

    # 3. 解释执行
    try:
        result = interpreter.execute(ast, source=source)
    except 返回信号:
        result = None
    return result, interpreter


# ========================
# 基本功能测试
# ========================


def test_pattern_macro_literal_match():
    """测试字面量模式匹配"""
    code = """
定义宏 描述(值) 匹配
    0 => 引述 "零"
    _ => 引述 "非零"

设 结果1 = !描述(0)
设 结果2 = !描述(5)
"""
    result, interpreter = run_code(code)
    assert interpreter.global_env.get("结果1") == "零"
    assert interpreter.global_env.get("结果2") == "非零"


def test_pattern_macro_variable_binding():
    """测试变量绑定模式"""
    code = """
定义宏 传递(值) 匹配
    x => 引述 $x

设 结果 = !传递(42)
"""
    result, interpreter = run_code(code)
    assert interpreter.global_env.get("结果") == 42


def test_pattern_macro_wildcard():
    """测试通配符模式"""
    code = """
定义宏 任意(值) 匹配
    _ => 引述 42

设 结果 = !任意(999)
"""
    result, interpreter = run_code(code)
    assert interpreter.global_env.get("结果") == 42


def test_pattern_macro_match_order():
    """测试多分支匹配顺序：第一个匹配成功的分支生效"""
    code = """
定义宏 检查(值) 匹配
    0 => 引述 "零"
    _ => 引述 "其他"

设 结果1 = !检查(0)
设 结果2 = !检查(1)
"""
    result, interpreter = run_code(code)
    assert interpreter.global_env.get("结果1") == "零"
    assert interpreter.global_env.get("结果2") == "其他"


# ========================
# 列表和字典解构测试
# ========================


def test_pattern_macro_list_destructure():
    """测试列表解构模式"""
    code = """
定义宏 头部(列表) 匹配
    [头, ...尾] => 引述 $头

设 结果 = !头部([10, 20, 30])
"""
    result, interpreter = run_code(code)
    assert interpreter.global_env.get("结果") == 10


def test_pattern_macro_fixed_list():
    """测试固定长度列表模式"""
    code = """
定义宏 求和(列表) 匹配
    [x, y] => 引述 $x + $y

设 结果 = !求和([3, 4])
"""
    result, interpreter = run_code(code)
    assert interpreter.global_env.get("结果") == 7


def test_pattern_macro_empty_list():
    """测试空列表模式"""
    code = """
定义宏 检查列表(值) 匹配
    [] => 引述 "空列表"
    _ => 引述 "非空列表"

设 结果1 = !检查列表([])
设 结果2 = !检查列表([1])
"""
    result, interpreter = run_code(code)
    assert interpreter.global_env.get("结果1") == "空列表"
    assert interpreter.global_env.get("结果2") == "非空列表"


def test_pattern_macro_dict_destructure():
    """测试字典解构模式"""
    code = """
定义宏 取名(数据) 匹配
    {"姓名": 名字} => 引述 $名字

设 结果 = !取名({"姓名": "张三"})
"""
    result, interpreter = run_code(code)
    assert interpreter.global_env.get("结果") == "张三"


# ========================
# 守卫条件测试
# ========================


def test_pattern_macro_guard():
    """测试守卫条件"""
    code = """
定义宏 分类(值) 匹配
    x 当 x > 0 => 引述 "正数"
    x 当 x < 0 => 引述 "负数"
    _ => 引述 "零"

设 结果1 = !分类(5)
设 结果2 = !分类(-3)
设 结果3 = !分类(0)
"""
    result, interpreter = run_code(code)
    assert interpreter.global_env.get("结果1") == "正数"
    assert interpreter.global_env.get("结果2") == "负数"
    assert interpreter.global_env.get("结果3") == "零"


# ========================
# 类型检查模式测试
# ========================


def test_pattern_macro_type_check():
    """测试类型检查模式"""
    code = """
定义宏 类型描述(值) 匹配
    类型:列表 => 引述 "是列表"
    类型:数值 => 引述 "是数值"
    _ => 引述 "其他"

设 结果1 = !类型描述([1, 2])
设 结果2 = !类型描述(42)
设 结果3 = !类型描述("hello")
"""
    result, interpreter = run_code(code)
    assert interpreter.global_env.get("结果1") == "是列表"
    assert interpreter.global_env.get("结果2") == "是数值"
    assert interpreter.global_env.get("结果3") == "其他"


# ========================
# 兼容性测试
# ========================


def test_pattern_macro_with_normal_macro():
    """测试模式匹配宏与普通宏共存"""
    code = """
定义宏 加一(x)
    返回 引述 $x + 1

定义宏 描述(值) 匹配
    0 => 引述 "零"
    _ => 引述 "非零"

设 结果1 = !加一(5)
设 结果2 = !描述(0)
"""
    result, interpreter = run_code(code)
    assert interpreter.global_env.get("结果1") == 6
    assert interpreter.global_env.get("结果2") == "零"


# ========================
# 错误处理测试
# ========================


def test_pattern_macro_no_match_error():
    """测试无匹配模式时报错"""
    code = """
定义宏 严格(值) 匹配
    0 => 引述 "零"

设 结果 = !严格(5)
"""
    with pytest.raises(Exception):
        run_code(code)


# ========================
# 模式匹配引擎单元测试
# ========================


def test_pattern_engine_literal():
    """测试模式匹配引擎：字面量匹配"""
    from dao.ast_nodes import NumberLiteral, StringLiteral, BooleanLiteral, NullLiteral
    from dao.macros.pattern_engine import PatternMatchEngine

    engine = PatternMatchEngine()

    # 数值匹配
    result = engine.match(NumberLiteral(value=0), 0)
    assert result.matched is True

    result = engine.match(NumberLiteral(value=0), 5)
    assert result.matched is False

    # 字符串匹配
    result = engine.match(StringLiteral(value="hello"), "hello")
    assert result.matched is True

    # 布尔匹配
    result = engine.match(BooleanLiteral(value=True), True)
    assert result.matched is True

    # 空值匹配
    result = engine.match(NullLiteral(), None)
    assert result.matched is True


def test_pattern_engine_variable_binding():
    """测试模式匹配引擎：变量绑定"""
    from dao.ast_nodes import Identifier
    from dao.macros.pattern_engine import PatternMatchEngine

    engine = PatternMatchEngine()

    result = engine.match(Identifier(name="x"), 42)
    assert result.matched is True
    assert result.bindings == {"x": 42}


def test_pattern_engine_wildcard():
    """测试模式匹配引擎：通配符"""
    from dao.ast_nodes import Identifier
    from dao.macros.pattern_engine import PatternMatchEngine

    engine = PatternMatchEngine()

    result = engine.match(Identifier(name="_"), 42)
    assert result.matched is True
    assert result.bindings == {}


def test_pattern_engine_list_pattern():
    """测试模式匹配引擎：列表解构"""
    from dao.ast_nodes import Identifier, ListPattern
    from dao.macros.pattern_engine import PatternMatchEngine

    engine = PatternMatchEngine()

    # 固定长度
    result = engine.match(
        ListPattern(elements=[Identifier(name="x"), Identifier(name="y")]),
        [1, 2],
    )
    assert result.matched is True
    assert result.bindings == {"x": 1, "y": 2}

    # 带展开
    result = engine.match(
        ListPattern(elements=[Identifier(name="头"), Identifier(name="尾")], has_spread=True),
        [1, 2, 3],
    )
    assert result.matched is True
    assert result.bindings == {"头": 1, "尾": [2, 3]}

    # 空列表
    result = engine.match(ListPattern(elements=[]), [])
    assert result.matched is True


def test_pattern_engine_dict_pattern():
    """测试模式匹配引擎：字典解构"""
    from dao.ast_nodes import Identifier, StringLiteral, DictPattern
    from dao.macros.pattern_engine import PatternMatchEngine

    engine = PatternMatchEngine()

    result = engine.match(
        DictPattern(pairs=[(StringLiteral(value="姓名"), Identifier(name="名字"))]),
        {"姓名": "张三"},
    )
    assert result.matched is True
    assert result.bindings == {"名字": "张三"}


def test_pattern_engine_type_check():
    """测试模式匹配引擎：类型检查"""
    from dao.ast_nodes import TypeCheckPattern
    from dao.macros.pattern_engine import PatternMatchEngine

    engine = PatternMatchEngine()

    result = engine.match(TypeCheckPattern(type_name="列表"), [1, 2])
    assert result.matched is True

    result = engine.match(TypeCheckPattern(type_name="数值"), "hello")
    assert result.matched is False

    result = engine.match(TypeCheckPattern(type_name="文本"), "hello")
    assert result.matched is True


# ========================
# 穷尽性检查器测试
# ========================


def test_exhaustiveness_checker():
    """测试穷尽性检查器"""
    from dao.ast_nodes import Identifier, NumberLiteral, PatternBranch, QuoteBlock
    from dao.macros.exhaustiveness import ExhaustivenessChecker

    checker = ExhaustivenessChecker()

    # 有通配符兜底：无警告
    branches = [
        PatternBranch(pattern=NumberLiteral(value=0), body=QuoteBlock()),
        PatternBranch(pattern=Identifier(name="_"), body=QuoteBlock()),
    ]
    warnings = checker.check(branches)
    assert len(warnings) == 0

    # 有变量绑定兜底：无警告
    branches = [
        PatternBranch(pattern=NumberLiteral(value=0), body=QuoteBlock()),
        PatternBranch(pattern=Identifier(name="x"), body=QuoteBlock()),
    ]
    warnings = checker.check(branches)
    assert len(warnings) == 0

    # 无兜底：有警告
    branches = [
        PatternBranch(pattern=NumberLiteral(value=0), body=QuoteBlock()),
    ]
    warnings = checker.check(branches)
    assert len(warnings) > 0

    # 空分支：有警告
    warnings = checker.check([])
    assert len(warnings) > 0


def test_exhaustiveness_boolean():
    """测试布尔类型的穷尽性检查"""
    from dao.ast_nodes import BooleanLiteral, NumberLiteral, PatternBranch, QuoteBlock
    from dao.macros.exhaustiveness import ExhaustivenessChecker

    checker = ExhaustivenessChecker()

    # 布尔类型穷尽：同时覆盖真和假，无警告
    branches = [
        PatternBranch(pattern=BooleanLiteral(value=True), body=QuoteBlock()),
        PatternBranch(pattern=BooleanLiteral(value=False), body=QuoteBlock()),
    ]
    warnings = checker.check(branches)
    assert len(warnings) == 0

    # 布尔类型不穷尽：只覆盖真，有警告
    branches = [
        PatternBranch(pattern=BooleanLiteral(value=True), body=QuoteBlock()),
    ]
    warnings = checker.check(branches)
    assert any("布尔" in w for w in warnings)

    # 布尔类型不穷尽：只覆盖假，有警告
    branches = [
        PatternBranch(pattern=BooleanLiteral(value=False), body=QuoteBlock()),
    ]
    warnings = checker.check(branches)
    assert any("布尔" in w for w in warnings)

    # 布尔类型不穷尽：缺少"假"
    branches = [
        PatternBranch(pattern=BooleanLiteral(value=True), body=QuoteBlock()),
        PatternBranch(pattern=NumberLiteral(value=0), body=QuoteBlock()),
    ]
    warnings = checker.check(branches)
    assert any("布尔" in w and "假" in w for w in warnings)


def test_exhaustiveness_guard():
    """测试守卫条件对穷尽性的影响"""
    from dao.ast_nodes import Identifier, NumberLiteral, PatternBranch, QuoteBlock
    from dao.macros.exhaustiveness import ExhaustivenessChecker

    checker = ExhaustivenessChecker()

    # 有守卫条件但无兜底：有警告
    branches = [
        PatternBranch(
            pattern=Identifier(name="x"),
            guard=Identifier(name="条件"),
            body=QuoteBlock(),
        ),
    ]
    warnings = checker.check(branches)
    assert any("守卫" in w for w in warnings)

    # 有守卫条件但有通配符兜底：无警告
    branches = [
        PatternBranch(
            pattern=Identifier(name="x"),
            guard=Identifier(name="条件"),
            body=QuoteBlock(),
        ),
        PatternBranch(pattern=Identifier(name="_"), body=QuoteBlock()),
    ]
    warnings = checker.check(branches)
    assert len(warnings) == 0

    # 多个守卫条件无兜底：有警告
    branches = [
        PatternBranch(
            pattern=Identifier(name="x"),
            guard=Identifier(name="条件1"),
            body=QuoteBlock(),
        ),
        PatternBranch(
            pattern=Identifier(name="y"),
            guard=Identifier(name="条件2"),
            body=QuoteBlock(),
        ),
    ]
    warnings = checker.check(branches)
    assert any("守卫" in w for w in warnings)


def test_exhaustiveness_enum():
    """测试枚举类型的穷尽性检查"""
    from dao.ast_nodes import EnumVariantPattern, PatternBranch, QuoteBlock
    from dao.macros.exhaustiveness import ExhaustivenessChecker

    checker = ExhaustivenessChecker()

    # 枚举变体模式：部分覆盖（由于无法确定总变体数，不会产生警告）
    branches = [
        PatternBranch(
            pattern=EnumVariantPattern(enum_name="结果", variant_name="成功"),
            body=QuoteBlock(),
        ),
        PatternBranch(
            pattern=EnumVariantPattern(enum_name="结果", variant_name="失败"),
            body=QuoteBlock(),
        ),
    ]
    warnings = checker.check(branches)
    # 枚举穷尽性检查不产生警告（无法确定总变体数）
    # 但由于没有通配符兜底，会有通用提示
    assert any("通配符" in w or "变量绑定" in w for w in warnings)


def test_exhaustiveness_mixed_patterns():
    """测试混合模式的穷尽性检查"""
    from dao.ast_nodes import (
        BooleanLiteral, NumberLiteral, StringLiteral,
        Identifier, PatternBranch, QuoteBlock,
    )
    from dao.macros.exhaustiveness import ExhaustivenessChecker

    checker = ExhaustivenessChecker()

    # 混合字面量模式无兜底：有警告
    branches = [
        PatternBranch(pattern=NumberLiteral(value=0), body=QuoteBlock()),
        PatternBranch(pattern=StringLiteral(value="hello"), body=QuoteBlock()),
        PatternBranch(pattern=BooleanLiteral(value=True), body=QuoteBlock()),
    ]
    warnings = checker.check(branches)
    assert len(warnings) > 0

    # 混合模式有通配符兜底：无警告
    branches = [
        PatternBranch(pattern=NumberLiteral(value=0), body=QuoteBlock()),
        PatternBranch(pattern=StringLiteral(value="hello"), body=QuoteBlock()),
        PatternBranch(pattern=Identifier(name="_"), body=QuoteBlock()),
    ]
    warnings = checker.check(branches)
    assert len(warnings) == 0


def test_exhaustiveness_variable_binding_no_guard():
    """测试变量绑定无守卫条件时视为穷尽"""
    from dao.ast_nodes import NumberLiteral, Identifier, PatternBranch, QuoteBlock
    from dao.macros.exhaustiveness import ExhaustivenessChecker

    checker = ExhaustivenessChecker()

    # 变量绑定无守卫：视为穷尽
    branches = [
        PatternBranch(pattern=NumberLiteral(value=0), body=QuoteBlock()),
        PatternBranch(pattern=Identifier(name="rest"), body=QuoteBlock()),
    ]
    warnings = checker.check(branches)
    assert len(warnings) == 0

    # 变量绑定有守卫：不视为穷尽
    branches = [
        PatternBranch(
            pattern=Identifier(name="x"),
            guard=Identifier(name="守卫"),
            body=QuoteBlock(),
        ),
    ]
    warnings = checker.check(branches)
    assert len(warnings) > 0


# ============================================================
# 模式匹配引擎深度单元测试
# ============================================================

from dao.ast_nodes import (
    NumberLiteral, StringLiteral, BooleanLiteral, NullLiteral,
    Identifier, ListPattern, DictPattern, TypeCheckPattern,
    EnumVariantPattern, PatternBranch, QuoteBlock,
)
from dao.macros.pattern_engine import (
    PatternType, MatchResult, PatternMatchEngine,
    DaoEnumProtocol, DictEnumAdapter, DaoStandardEnumAdapter,
    DuckTypeEnumAdapter, adapt_to_enum_protocol,
    classify_pattern, describe_pattern, _extract_object_value,
)


class _MyEnum(DaoEnumProtocol):
    @property
    def dao_class_name(self):
        return "结果"

    @property
    def dao_variant_name(self):
        return "成功"

    @property
    def dao_inner_value(self):
        return 42


def test_pattern_type_and_classify():
    assert classify_pattern(NumberLiteral(value=1)) == PatternType.LITERAL
    assert classify_pattern(StringLiteral(value="a")) == PatternType.LITERAL
    assert classify_pattern(BooleanLiteral(value=True)) == PatternType.LITERAL
    assert classify_pattern(NullLiteral()) == PatternType.LITERAL
    assert classify_pattern(Identifier(name="_")) == PatternType.WILDCARD
    assert classify_pattern(Identifier(name="x")) == PatternType.VARIABLE_BINDING
    assert classify_pattern(ListPattern()) == PatternType.LIST_DESTRUCTURE
    assert classify_pattern(DictPattern()) == PatternType.DICT_DESTRUCTURE
    assert classify_pattern(TypeCheckPattern(type_name="数值")) == PatternType.TYPE_CHECK
    assert classify_pattern(EnumVariantPattern()) == PatternType.ENUM_VARIANT
    assert classify_pattern(object()) == PatternType.UNKNOWN
    assert PatternType.LITERAL.value == "字面量"


def test_describe_pattern():
    assert "字面量模式: 1" in describe_pattern(NumberLiteral(value=1))
    assert '字面量模式: "a"' in describe_pattern(StringLiteral(value="a"))
    assert "真" in describe_pattern(BooleanLiteral(value=True))
    assert "假" in describe_pattern(BooleanLiteral(value=False))
    assert "空" in describe_pattern(NullLiteral())
    assert "通配符模式" in describe_pattern(Identifier(name="_"))
    assert "变量绑定模式: x" in describe_pattern(Identifier(name="x"))
    assert "列表解构模式" in describe_pattern(ListPattern(elements=[Identifier(name="x")]))
    assert "展开操作符" in describe_pattern(
        ListPattern(elements=[Identifier(name="x")], has_spread=True)
    )
    assert "枚举变体模式" in describe_pattern(
        EnumVariantPattern(enum_name="结果", variant_name="成功", binding="v")
    )
    assert "类型检查模式" in describe_pattern(TypeCheckPattern(type_name="数值"))
    assert "未知模式" in describe_pattern(object())


def test_describe_pattern_nested():
    desc = describe_pattern(DictPattern(pairs=[
        (StringLiteral(value="k"), ListPattern(elements=[Identifier(name="x")])),
        (NumberLiteral(value=1), Identifier(name="y")),
        (BooleanLiteral(value=True), Identifier(name="z")),
        (NullLiteral(), Identifier(name="w")),
        (Identifier(name="key"), Identifier(name="q")),  # 非字面量键 → '?'
    ]))
    assert "字典解构模式" in desc and "列表解构模式" in desc
    assert "?" in desc and "通配符" not in desc


def test_enum_adapters():
    data = {"__type__": "enum", "类": "结果", "变体": "成功", "值": 7}
    assert DictEnumAdapter.can_adapt(data) is True
    assert DictEnumAdapter.can_adapt({"a": 1}) is False
    adapter = DictEnumAdapter(data)
    assert adapter.dao_class_name == "结果"
    assert adapter.dao_variant_name == "成功"
    assert adapter.dao_inner_value == 7
    assert adapter.matches_enum("结果", "成功") is True

    class Std:
        __dao_class__ = "颜色"
        __variant__ = "红"

        def __init__(self):
            self._value = 9

    std_adapter = DaoStandardEnumAdapter(Std())
    assert std_adapter.dao_class_name == "颜色"
    assert std_adapter.dao_variant_name == "红"
    assert std_adapter.dao_inner_value == 9

    class 苹果:
        def __init__(self):
            self.值 = 5

    duck = DuckTypeEnumAdapter(苹果())
    assert duck.dao_class_name == "苹果" and duck.dao_variant_name == "苹果"
    assert duck.dao_inner_value == 5
    assert DuckTypeEnumAdapter.can_adapt(苹果()) is True
    assert DuckTypeEnumAdapter.can_adapt({"a": 1}) is False
    assert DuckTypeEnumAdapter.can_adapt(_MyEnum()) is False


def test_adapt_to_enum_protocol():
    my = _MyEnum()
    assert adapt_to_enum_protocol(my) is my

    class Std:
        __dao_class__ = "颜色"
        __variant__ = "红"

    assert isinstance(adapt_to_enum_protocol(Std()), DaoStandardEnumAdapter)
    assert isinstance(
        adapt_to_enum_protocol({"__type__": "enum", "类": "结果", "变体": "成功"}),
        DictEnumAdapter,
    )

    class 苹果:
        pass

    assert isinstance(adapt_to_enum_protocol(苹果()), DuckTypeEnumAdapter)
    assert adapt_to_enum_protocol({"a": 1}) is None


def test_extract_object_value():
    class A:
        def __init__(self):
            self._value = 1

    class B:
        def __init__(self):
            self.值 = 2

    class C:
        __dao_class__ = "x"
        __variant__ = "y"

        def __init__(self):
            self.foo = 3

    assert _extract_object_value(A()) == 1
    assert _extract_object_value(B()) == 2
    assert _extract_object_value(C()) == 3
    assert _extract_object_value(42) == 42
    assert _MyEnum().matches_enum("结果", "成功") is True


def test_match_result():
    ok = MatchResult.success({"x": 1})
    assert ok.matched is True and ok.bindings == {"x": 1}
    fail = MatchResult.failure("原因")
    assert fail.matched is False and fail.failure_reason == "原因"
    merged = ok.merge(MatchResult.success({"y": 2}))
    assert merged.matched is True and merged.bindings == {"x": 1, "y": 2}
    assert fail.merge(ok).matched is False
    assert ok.merge(fail).matched is False
    assert fail.merge(ok).failure_reason == "原因"
    assert ok.merge(fail).failure_reason == "原因"
    assert MatchResult.success().bindings == {}
    base = MatchResult(matched=True, bindings={"a": 1})
    assert base.merge(MatchResult.success({"b": 2})).bindings == {"a": 1, "b": 2}


def test_match_with_guard():
    engine = PatternMatchEngine()
    assert engine.match_with_guard(Identifier(name="x"), 5, lambda b: b["x"] > 0).matched is True
    r = engine.match_with_guard(Identifier(name="x"), 5, lambda b: b["x"] > 10)
    assert r.matched is False and r.failure_reason == "守卫条件不满足"
    r = engine.match_with_guard(Identifier(name="x"), 5, lambda b: 1 / 0)
    assert r.matched is False and "守卫条件求值失败" in r.failure_reason
    # 模式本身不匹配时直接返回，不求值守卫
    r = engine.match_with_guard(NumberLiteral(value=1), 2, lambda b: True)
    assert r.matched is False
    # 未提供守卫函数
    assert engine.match_with_guard(Identifier(name="x"), 5).matched is True


def test_match_branches():
    engine = PatternMatchEngine()
    branches = [
        PatternBranch(pattern=NumberLiteral(value=1), body=QuoteBlock()),
        PatternBranch(pattern=Identifier(name="x"), guard=Identifier(name="g"), body=QuoteBlock()),
        PatternBranch(pattern=Identifier(name="_"), body=QuoteBlock()),
    ]
    b, _ = engine.match_branches(branches, 1)
    assert b is branches[0]
    b, _ = engine.match_branches(branches, 5, guard_evaluator=lambda g, binds, env: False)
    assert b is branches[2]
    b, _ = engine.match_branches(branches, 5, guard_evaluator=lambda g, binds, env: 1 / 0)
    assert b is branches[2]
    b, _ = engine.match_branches(branches, 5, guard_evaluator=lambda g, binds, env: True)
    assert b is branches[1]
    b, r = engine.match_branches(
        [PatternBranch(pattern=NumberLiteral(value=1), body=QuoteBlock())], 9
    )
    assert b is None and r.matched is False


def test_match_tuple_and_unsupported():
    engine = PatternMatchEngine()
    r = engine.match_tuple([Identifier(name="a"), Identifier(name="b")], [1, 2])
    assert r.matched is True and r.bindings == {"a": 1, "b": 2}
    r = engine.match_tuple([Identifier(name="a")], [1, 2])
    assert r.matched is False and "参数数量不匹配" in r.failure_reason
    r = engine.match_tuple([NumberLiteral(value=1), Identifier(name="b")], [2, 3])
    assert r.matched is False
    r = engine.match(object(), 1)
    assert r.matched is False and "不支持的模式类型" in r.failure_reason


def test_match_list_pattern_failures():
    engine = PatternMatchEngine()
    assert "不是列表" in engine.match(ListPattern(elements=[Identifier(name="x")]), "abc").failure_reason
    r = engine.match(ListPattern(elements=[Identifier(name="x"), Identifier(name="y")]), [1])
    assert r.matched is False and "长度不匹配" in r.failure_reason
    r = engine.match(ListPattern(elements=[NumberLiteral(value=1)]), [2])
    assert r.matched is False and "第 0 个元素不匹配" in r.failure_reason
    r = engine.match(ListPattern(elements=[]), [1])
    assert r.matched is False and "空列表模式不匹配" in r.failure_reason
    r = engine.match(
        ListPattern(elements=[Identifier(name="a"), Identifier(name="b"), Identifier(name="rest")],
                    has_spread=True),
        [1],
    )
    assert r.matched is False and "长度不足" in r.failure_reason
    r = engine.match(
        ListPattern(elements=[NumberLiteral(value=1), Identifier(name="rest")], has_spread=True),
        [2, 3],
    )
    assert r.matched is False and "第 0 个元素不匹配" in r.failure_reason


def test_match_dict_pattern_failures():
    engine = PatternMatchEngine()
    r = engine.match(DictPattern(pairs=[(StringLiteral(value="k"), Identifier(name="v"))]), [1])
    assert r.matched is False and "不是字典" in r.failure_reason
    assert engine.match(DictPattern(pairs=[]), {"a": 1}).matched is True
    r = engine.match(DictPattern(pairs=[(Identifier(name="k"), Identifier(name="v"))]), {"k": 1})
    assert r.matched is False and "字典键不是字面量" in r.failure_reason
    r = engine.match(DictPattern(pairs=[(StringLiteral(value="k"), Identifier(name="v"))]), {"other": 1})
    assert r.matched is False and "缺少键" in r.failure_reason
    r = engine.match(DictPattern(pairs=[(StringLiteral(value="k"), NumberLiteral(value=1))]), {"k": 2})
    assert r.matched is False and "的值不匹配" in r.failure_reason
    r = engine.match(DictPattern(pairs=[(NullLiteral(), Identifier(name="v"))]), {None: 1})
    assert r.matched is True and r.bindings == {"v": 1}


def test_match_type_pattern_all():
    engine = PatternMatchEngine()
    assert engine.match(TypeCheckPattern(type_name="列表"), [1]).matched is True
    assert engine.match(TypeCheckPattern(type_name="字典"), {}).matched is True
    assert engine.match(TypeCheckPattern(type_name="数值"), 1).matched is True
    assert engine.match(TypeCheckPattern(type_name="数值"), 1.5).matched is True
    assert engine.match(TypeCheckPattern(type_name="文本"), "x").matched is True
    assert engine.match(TypeCheckPattern(type_name="布尔"), True).matched is True
    assert engine.match(TypeCheckPattern(type_name="函数"), lambda: 1).matched is True
    r = engine.match(TypeCheckPattern(type_name="数值"), True)
    assert r.matched is False and "布尔值不属于数值" in r.failure_reason
    r = engine.match(TypeCheckPattern(type_name="未知"), 1)
    assert r.matched is False and "未知类型名" in r.failure_reason
    r = engine.match(TypeCheckPattern(type_name="列表"), {})
    assert r.matched is False and "类型检查不匹配" in r.failure_reason


def test_match_enum_variant():
    engine = PatternMatchEngine()
    pat = EnumVariantPattern(enum_name="结果", variant_name="成功", binding="v")
    r = engine.match(pat, {"__type__": "enum", "类": "结果", "变体": "成功", "值": 42})
    assert r.matched is True and r.bindings == {"v": 42}
    r = engine.match(pat, _MyEnum())
    assert r.matched is True and r.bindings == {"v": 42}

    class 结果:
        pass

    r = engine.match(
        EnumVariantPattern(enum_name="结果", variant_name="结果", binding="v"), 结果()
    )
    assert r.matched is True and "v" in r.bindings
    r = engine.match(EnumVariantPattern(enum_name="结果", variant_name="失败"), _MyEnum())
    assert r.matched is False and "枚举变体不匹配" in r.failure_reason
    r = engine.match(pat, {"a": 1})
    assert r.matched is False and "无法适配" in r.failure_reason
    r = engine.match(EnumVariantPattern(enum_name="结果", variant_name="成功"), _MyEnum())
    assert r.matched is True and r.bindings == {}

    class EmptyEnum(DaoEnumProtocol):
        @property
        def dao_class_name(self):
            return "结果"

        @property
        def dao_variant_name(self):
            return "成功"

    r = engine.match(
        EnumVariantPattern(enum_name="结果", variant_name="成功", binding="v"),
        EmptyEnum(),
    )
    assert r.matched is True and "v" in r.bindings


def test_match_literal_failures():
    engine = PatternMatchEngine()
    assert "字符串不匹配" in engine.match(StringLiteral(value="a"), "b").failure_reason
    assert "布尔值不匹配" in engine.match(BooleanLiteral(value=True), False).failure_reason
    assert "空值不匹配" in engine.match(NullLiteral(), 1).failure_reason
    assert "数值不匹配" in engine.match(NumberLiteral(value=1), 2).failure_reason
    r = engine._match_literal(object(), 1)
    assert r.matched is False and "未知字面量类型" in r.failure_reason
