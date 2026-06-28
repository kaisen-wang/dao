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
