"""
宏系统测试模块
测试道语言的宏系统功能
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


def test_macro_basic_functionality():
    """测试基本宏功能"""
    code = """
定义宏 加一(x)
    返回 引述 $x + 1

设 结果 = !加一(5)
"""
    result, interpreter = run_code(code)
    assert interpreter.global_env.get("结果") == 6


def test_macro_with_block():
    """测试带块的宏"""
    code = """
定义宏 循环(n, 块)
    返回 引述
        设 i = 0
        当 i < $n
            $块
            i = i + 1

设 总和 = 0
!循环(5)
    总和 = 总和 + i
"""
    result, interpreter = run_code(code)
    assert interpreter.global_env.get("总和") == 10


def test_quote_unquote():
    """测试引述和反引述表达式"""
    code = """
定义宏 构建表达式(a, b)
    返回 引述
        $a * $b + $a

设 结果 = !构建表达式(2, 3)
"""
    result, interpreter = run_code(code)
    assert interpreter.global_env.get("结果") == 2 * 3 + 2


def test_hygienic_macro():
    """测试卫生宏"""
    code = """
定义宏 卫生测试(x)
    返回 引述
        设 temp = $x * 2
        temp

设 temp = 10
设 结果 = !卫生测试(5)
"""
    result, interpreter = run_code(code)
    assert interpreter.global_env.get("结果") == 10
    assert interpreter.global_env.get("temp") == 10


def test_macro_with_multiple_params():
    """测试多参数宏"""
    code = """
定义宏 计算(a, b, c)
    返回 引述
        ($a + $b) * $c

设 结果 = !计算(1, 2, 3)
"""
    result, interpreter = run_code(code)
    assert interpreter.global_env.get("结果") == (1 + 2) * 3


def test_macro_with_optional_params():
    """测试可选参数宏"""
    code = """
定义宏 可选参数(x, y=10)
    返回 引述
        $x + $y

设 结果1 = !可选参数(5)
设 结果2 = !可选参数(5, 20)
"""
    result, interpreter = run_code(code)
    assert interpreter.global_env.get("结果1") == 15
    assert interpreter.global_env.get("结果2") == 25


def test_macro_recursion():
    """测试递归宏"""
    code = """
定义宏 递归宏(n)
    返回 引述
        如果 $n == 0
            0
        否则
            $n + !递归宏($n - 1)

设 结果 = !递归宏(5)
"""
    result, interpreter = run_code(code)
    assert interpreter.global_env.get("结果") == 15


def test_macro_injection():
    """测试宏注入"""
    code = """
定义宏 注入宏()
    设 a = 1
    设 b = 2
    返回 引述 1 + 2

设 注入结果 = !注入宏()
"""
    result, interpreter = run_code(code)
    assert interpreter.global_env.get("注入结果") == 3


def test_macro_with_pipe():
    """测试管道操作符与宏结合"""
    code = """
定义宏 平方(x)
    返回 引述 $x * $x

定义宏 加五(x)
    返回 引述 $x + 5

设 结果 = 3 |> 平方 |> 加五
"""
    result, interpreter = run_code(code)
    assert interpreter.global_env.get("结果") == 3 * 3 + 5


# ==================== 新增测试 ====================


def test_macro_undefined_error():
    """测试调用未定义的宏时报错"""
    code = """
设 结果 = !不存在的宏(5)
"""
    from dao.errors import 运行时错误
    with pytest.raises(运行时错误, match="未找到宏定义"):
        run_code(code)


def test_macro_redefinition_error():
    """测试同一作用域内重复定义同名宏报错"""
    code = """
定义宏 测试(x)
    返回 引述 $x + 1

定义宏 测试(y)
    返回 引述 $y + 2
"""
    from dao.errors import 宏展开错误
    with pytest.raises(宏展开错误, match="已在当前作用域中定义"):
        run_code(code)


def test_macro_scope_management():
    """测试宏注册表作用域管理"""
    from dao.macros.registry import MacroRegistry

    registry = MacroRegistry()
    registry.clear()

    assert registry.get_macro_count() == 0

    registry.enter_scope()
    assert registry._scope_depth == 1

    registry.leave_scope()
    assert registry._scope_depth == 0


def test_macro_hygiene_no_capture():
    """测试卫生宏不捕获外部变量"""
    code = """
定义宏 交换(a, b)
    返回 引述
        设 _temp = $a
        $a

设 _temp = 100
设 结果 = !交换(5, 10)
"""
    result, interpreter = run_code(code)
    assert interpreter.global_env.get("_temp") == 100


def test_macro_multiple_calls():
    """测试同一宏多次调用"""
    code = """
定义宏 双倍(x)
    返回 引述 $x * 2

设 结果1 = !双倍(3)
设 结果2 = !双倍(7)
设 结果3 = !双倍(0)
"""
    result, interpreter = run_code(code)
    assert interpreter.global_env.get("结果1") == 6
    assert interpreter.global_env.get("结果2") == 14
    assert interpreter.global_env.get("结果3") == 0


def test_macro_nested_arithmetic():
    """测试宏展开结果参与复杂运算"""
    code = """
定义宏 平方(x)
    返回 引述 $x * $x

设 a = !平方(3)
设 b = !平方(4)
设 结果 = a + b
"""
    result, interpreter = run_code(code)
    assert interpreter.global_env.get("结果") == 9 + 16


def test_macro_string_argument():
    """测试宏接受字符串参数"""
    code = """
定义宏 问候(名字)
    返回 引述 $名字

设 结果 = !问候("世界")
"""
    result, interpreter = run_code(code)
    assert interpreter.global_env.get("结果") == "世界"


def test_macro_boolean_argument():
    """测试宏接受布尔参数"""
    code = """
定义宏 取反(条件)
    返回 引述 不是 $条件

设 结果 = !取反(真)
"""
    result, interpreter = run_code(code)
    assert interpreter.global_env.get("结果") == False
