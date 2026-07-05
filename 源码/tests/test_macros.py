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


# ==================== 内置宏测试 ====================


def test_builtin_macro_除非():
    """测试内置宏 @除非"""
    code = """
设 温度 = 15
设 冷 = 假
!除非(温度 > 20)
    冷 = 真
"""
    result, interpreter = run_code(code)
    assert interpreter.global_env.get("冷") == True


def test_builtin_macro_除非_false():
    """测试内置宏 @除非 条件为真时不执行"""
    code = """
设 温度 = 25
设 冷 = 假
!除非(温度 > 20)
    冷 = 真
"""
    result, interpreter = run_code(code)
    assert interpreter.global_env.get("冷") == False


def test_builtin_macro_日志():
    """测试内置宏 @日志"""
    code = """
设 值 = 0
!日志("测试函数")
    值 = 42
"""
    result, interpreter = run_code(code)
    assert interpreter.global_env.get("值") == 42


def test_builtin_macro_延迟():
    """测试内置宏 @延迟"""
    code = """
设 计数 = 0
设 结果 = !延迟(计数 + 1)
"""
    result, interpreter = run_code(code)
    # 延迟宏应返回计算结果
    assert result == 1


def test_builtin_macro_缓存():
    """测试内置宏 @缓存"""
    code = """
设 _缓存表 = {}
设 调用次数 = 0
设 结果1 = !缓存("键1")
    调用次数 = 调用次数 + 1
    调用次数
设 结果2 = !缓存("键1")
    调用次数 = 调用次数 + 1
    调用次数
"""
    result, interpreter = run_code(code)
    # 第一次缓存未命中，执行代码块；第二次命中，直接返回缓存
    assert interpreter.global_env.get("结果1") == 1


def test_builtin_macro_registration():
    """测试内置宏注册"""
    from dao.macros.builtins import register_builtin_macros
    from dao.macros.registry import MacroRegistry

    registry = MacroRegistry()
    registry.clear()
    register_builtin_macros(registry)

    # 验证所有内置宏都已注册
    assert registry.find_macro("除非") is not None
    assert registry.find_macro("计时") is not None
    assert registry.find_macro("重试") is not None
    assert registry.find_macro("日志") is not None
    assert registry.find_macro("缓存") is not None
    assert registry.find_macro("延迟") is not None


def test_builtin_macro_user_override():
    """测试用户定义的宏可以覆盖内置宏"""
    code = """
定义宏 除非(条件, 代码块)
    返回 引述
        如果 $条件
            $代码块

设 结果 = 假
!除非(真)
    结果 = 真
"""
    result, interpreter = run_code(code)
    # 用户定义的除非宏：条件为真时执行（与内置相反）
    assert interpreter.global_env.get("结果") == True


# ==================== @计时 宏专项测试 ====================


def test_builtin_macro_计时_expansion():
    """测试内置宏 @计时 展开后的 AST 结构"""
    from dao.macros.builtins import register_builtin_macros
    from dao.macros.registry import MacroRegistry
    from dao.macros.expander import MacroExpander
    from dao.ast_nodes import (
        Identifier, StringLiteral, NumberLiteral, BinaryOp, MacroCall,
        VariableDecl, FunctionCall, ExpressionStmt, ReturnStmt, QuoteBlock,
    )

    registry = MacroRegistry()
    registry.clear()
    register_builtin_macros(registry)

    expander = MacroExpander()
    expander.registry = registry

    # 构造宏调用：!计时("排序", 排序(数据))
    call = MacroCall(
        name="计时",
        arguments=[
            StringLiteral(value="排序"),
            FunctionCall(
                callee=Identifier(name="排序"),
                arguments=[Identifier(name="数据")],
            ),
        ],
    )

    # 展开宏
    expanded = expander._expand_macro_call(call, 0)

    # 验证展开结果为 QuoteBlock
    assert isinstance(expanded, QuoteBlock)
    body = expanded.body

    # 验证展开结构：5个语句
    # 1. 设 _计时开始 = 时间()
    # 2. 设 _计时结果 = 代码块
    # 3. 设 _计时结束 = 时间()
    # 4. 打印(标签, "耗时:", _计时结束 - _计时开始, "秒")
    # 5. 返回 _计时结果
    assert len(body) == 5
    assert isinstance(body[0], VariableDecl)
    assert body[0].name == "_计时开始"
    assert isinstance(body[1], VariableDecl)
    assert body[1].name == "_计时结果"
    assert isinstance(body[2], VariableDecl)
    assert body[2].name == "_计时结束"
    assert isinstance(body[3], ExpressionStmt)
    assert isinstance(body[4], ReturnStmt)


def test_builtin_macro_计时_parameter_replacement():
    """测试内置宏 @计时 参数替换"""
    from dao.macros.builtins import register_builtin_macros
    from dao.macros.registry import MacroRegistry
    from dao.macros.expander import MacroExpander
    from dao.ast_nodes import (
        Identifier, StringLiteral, NumberLiteral, MacroCall, QuoteBlock,
        VariableDecl, FunctionCall,
    )

    registry = MacroRegistry()
    registry.clear()
    register_builtin_macros(registry)

    expander = MacroExpander()
    expander.registry = registry

    # 构造宏调用：!计时("测试标签", 42)
    call = MacroCall(
        name="计时",
        arguments=[
            StringLiteral(value="测试标签"),
            NumberLiteral(value=42),
        ],
    )

    expanded = expander._expand_macro_call(call, 0)
    assert isinstance(expanded, QuoteBlock)

    # 验证标签参数被替换
    body = expanded.body
    # 第4个语句是打印，其第一个参数应为 "测试标签"
    print_stmt = body[3]
    from dao.ast_nodes import ExpressionStmt
    assert isinstance(print_stmt, ExpressionStmt)
    call_node = print_stmt.expression
    assert isinstance(call_node, FunctionCall)
    # 第一个参数是标签，参数替换后直接变为 StringLiteral("测试标签")
    # （原始宏体中 BinaryOp(">>> 进入: " + 标签) 的 标签 被替换为实参后，
    #   如果实参是 StringLiteral，BinaryOp 可能被优化为 StringLiteral）
    first_arg = call_node.arguments[0]
    assert isinstance(first_arg, StringLiteral)
    assert first_arg.value == "测试标签"


def test_builtin_macro_计时_default_label():
    """测试内置宏 @计时 默认标签参数"""
    from dao.macros.builtins import register_builtin_macros
    from dao.macros.registry import MacroRegistry
    from dao.macros.expander import MacroExpander
    from dao.ast_nodes import (
        Identifier, NumberLiteral, MacroCall, QuoteBlock,
    )

    registry = MacroRegistry()
    registry.clear()
    register_builtin_macros(registry)

    expander = MacroExpander()
    expander.registry = registry

    # 构造宏调用：!计时(42) — 只传代码块，标签使用默认值
    call = MacroCall(
        name="计时",
        arguments=[
            NumberLiteral(value=42),
        ],
    )

    expanded = expander._expand_macro_call(call, 0)
    # 展开应成功（即使只有一个参数，标签使用默认值 ""）
    assert expanded is not None


# ==================== @重试 宏专项测试 ====================


def test_builtin_macro_重试_expansion():
    """测试内置宏 @重试 展开后的 AST 结构"""
    from dao.macros.builtins import register_builtin_macros
    from dao.macros.registry import MacroRegistry
    from dao.macros.expander import MacroExpander
    from dao.ast_nodes import (
        Identifier, NumberLiteral, MacroCall, QuoteBlock,
        VariableDecl, WhileStmt, TryStmt, ReturnStmt, FunctionCall,
    )

    registry = MacroRegistry()
    registry.clear()
    register_builtin_macros(registry)

    expander = MacroExpander()
    expander.registry = registry

    # 构造宏调用：!重试(3, 连接服务器())
    call = MacroCall(
        name="重试",
        arguments=[
            NumberLiteral(value=3),
            FunctionCall(
                callee=Identifier(name="连接服务器"),
            ),
        ],
    )

    # 展开宏
    expanded = expander._expand_macro_call(call, 0)

    # 验证展开结果为 QuoteBlock
    assert isinstance(expanded, QuoteBlock)
    body = expanded.body

    # 验证展开结构：4个语句
    # 1. 设 _重试次数 = 0
    # 2. 设 _重试结果 = 空
    # 3. 当 _重试次数 < 次数 ... (WhileStmt with TryStmt)
    # 4. 返回 _重试结果
    assert len(body) == 4
    assert isinstance(body[0], VariableDecl)
    assert body[0].name == "_重试次数"
    assert isinstance(body[1], VariableDecl)
    assert body[1].name == "_重试结果"
    assert isinstance(body[2], WhileStmt)
    assert isinstance(body[3], ReturnStmt)


def test_builtin_macro_重试_parameter_replacement():
    """测试内置宏 @重试 参数替换"""
    from dao.macros.builtins import register_builtin_macros
    from dao.macros.registry import MacroRegistry
    from dao.macros.expander import MacroExpander
    from dao.ast_nodes import (
        Identifier, NumberLiteral, MacroCall, QuoteBlock,
        WhileStmt, BinaryOp,
    )

    registry = MacroRegistry()
    registry.clear()
    register_builtin_macros(registry)

    expander = MacroExpander()
    expander.registry = registry

    # 构造宏调用：!重试(5, 代码块)
    call = MacroCall(
        name="重试",
        arguments=[
            NumberLiteral(value=5),
            Identifier(name="代码块"),
        ],
    )

    expanded = expander._expand_macro_call(call, 0)
    assert isinstance(expanded, QuoteBlock)

    # 验证次数参数被替换
    body = expanded.body
    # WhileStmt 的条件是 _重试次数 < 次数
    # 次数参数应被替换为 NumberLiteral(5)
    while_stmt = body[2]
    assert isinstance(while_stmt, WhileStmt)
    condition = while_stmt.condition
    assert isinstance(condition, BinaryOp)
    assert condition.operator == "<"
    # 右侧应为 NumberLiteral(5)（替换后的次数参数）
    assert isinstance(condition.right, NumberLiteral)
    assert condition.right.value == 5


def test_builtin_macro_重试_default_count():
    """测试内置宏 @重试 默认次数参数"""
    from dao.macros.builtins import register_builtin_macros
    from dao.macros.registry import MacroRegistry
    from dao.macros.expander import MacroExpander
    from dao.ast_nodes import (
        Identifier, MacroCall, QuoteBlock,
    )

    registry = MacroRegistry()
    registry.clear()
    register_builtin_macros(registry)

    expander = MacroExpander()
    expander.registry = registry

    # 构造宏调用：!重试(代码块) — 只传代码块，次数使用默认值 3
    call = MacroCall(
        name="重试",
        arguments=[
            Identifier(name="代码块"),
        ],
    )

    expanded = expander._expand_macro_call(call, 0)
    # 展开应成功
    assert expanded is not None
