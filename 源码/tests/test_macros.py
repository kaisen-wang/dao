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
    assert interpreter.global_env.get("结果") == 1


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
    assert body[0].name.startswith("_计时开始")
    assert isinstance(body[1], VariableDecl)
    assert body[1].name.startswith("_计时结果")
    assert isinstance(body[2], VariableDecl)
    assert body[2].name.startswith("_计时结束")
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
    assert body[0].name.startswith("_重试次数")
    assert isinstance(body[1], VariableDecl)
    assert body[1].name.startswith("_重试结果")
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


# ============================================================
# AST 操作工具（ast_ops.py）单元测试
# ============================================================

from dao.macros.ast_ops import ASTOperations, _iter_data_fields
from dao.ast_nodes import (
    Program, ExpressionStmt, Identifier, NumberLiteral, StringLiteral,
    BooleanLiteral, NullLiteral, BinaryOp, VariableDecl, ListLiteral,
    QuoteBlock,
)


def _fresh_tree():
    """构造一棵用于 AST 操作测试的树（每次调用返回新对象）"""
    return Program(statements=[
        ExpressionStmt(expression=BinaryOp(
            left=Identifier(name="$x"), operator="+", right=NumberLiteral(value=1),
        )),
        VariableDecl(name="y", value=Identifier(name="$x")),
    ])


def test_ast_iter_data_fields():
    node = Identifier(name="x", line=3, column=4)
    fields = dict(_iter_data_fields(node))
    assert "name" in fields
    assert "line" not in fields and "column" not in fields
    # 非 dataclass 对象没有数据字段
    assert list(_iter_data_fields(123)) == []
    assert list(_iter_data_fields("abc")) == []


def test_ast_replace_variables():
    node = Identifier(name="$x")
    # 空替换表 / None 节点
    assert ASTOperations.replace_variables(node, {}) is node
    assert ASTOperations.replace_variables(None, {"x": NumberLiteral(value=1)}) is None
    # 基本替换（含 $ 前缀）递归到子节点
    tree = _fresh_tree()
    result = ASTOperations.replace_variables(tree, {"x": NumberLiteral(value=99)})
    assert result.statements[0].expression.left.value == 99
    assert result.statements[1].value.value == 99
    # 列表处理
    nodes = [Identifier(name="$a"), Identifier(name="$b"), None]
    result = ASTOperations.replace_variables(
        nodes, {"a": NumberLiteral(value=1), "b": NumberLiteral(value=2)}
    )
    assert result[0].value == 1 and result[1].value == 2 and result[2] is None


def test_ast_find_nodes():
    tree = _fresh_tree()
    names = [i.name for i in ASTOperations.find_nodes(tree, Identifier)]
    assert "$x" in names and "y" not in names
    assert ASTOperations.find_nodes(None, Identifier) == []
    assert len(ASTOperations.find_nodes([Identifier(name="a"), Identifier(name="b")], Identifier)) == 2


def test_ast_find_node_by_condition():
    tree = _fresh_tree()
    found = ASTOperations.find_node_by_condition(
        tree, lambda n: isinstance(n, NumberLiteral) and n.value == 1
    )
    assert len(found) == 1
    assert ASTOperations.find_node_by_condition(tree, lambda n: False) == []
    assert ASTOperations.find_node_by_condition(None, lambda n: True) == []
    assert len(ASTOperations.find_node_by_condition(
        [Identifier(name="a")], lambda n: isinstance(n, Identifier)
    )) == 1


def test_ast_replace_node():
    target = Identifier(name="old")
    tree = Program(statements=[ExpressionStmt(expression=target)])
    replacement = NumberLiteral(value=7)
    result = ASTOperations.replace_node(tree, target, replacement)
    assert result.statements[0].expression is replacement
    assert ASTOperations.replace_node(target, target, replacement) is replacement
    assert ASTOperations.replace_node(None, target, replacement) is None
    assert ASTOperations.replace_node([target], target, replacement)[0] is replacement


def test_ast_modify_node():
    tree = _fresh_tree()
    result = ASTOperations.modify_node(
        tree, BinaryOp, lambda n: setattr(n, "operator", "*") or n
    )
    assert result.statements[0].expression.operator == "*"
    # 顶层即目标类型
    assert ASTOperations.modify_node(
        NumberLiteral(value=1), NumberLiteral, lambda n: NumberLiteral(value=2)
    ).value == 2
    assert ASTOperations.modify_node(None, NumberLiteral, lambda n: n) is None
    assert ASTOperations.modify_node([NumberLiteral(value=1)], NumberLiteral, lambda n: n)[0].value == 1


def test_ast_extract_node_info():
    info = ASTOperations.extract_node_info(Identifier(name="abc", line=5, column=6))
    assert info["type"] == "Identifier"
    assert info["line"] == 5 and info["column"] == 6
    assert info["name"] == "abc"
    info2 = ASTOperations.extract_node_info([Identifier(name="a")])
    assert info2["type"] == "list"


def test_ast_validate_node():
    tree = _fresh_tree()
    assert ASTOperations.validate_node(
        tree, lambda n: isinstance(n, NumberLiteral) and n.value == 1
    ) is True
    assert ASTOperations.validate_node(tree, lambda n: isinstance(n, StringLiteral)) is False
    assert ASTOperations.validate_node(tree, lambda n: True) is True
    assert ASTOperations.validate_node(None, lambda n: n is not None) is False


def test_ast_traverse_node():
    tree = _fresh_tree()
    pre, post = [], []
    result = ASTOperations.traverse_node(
        tree,
        lambda n: pre.append(type(n).__name__) or n,
        lambda n: post.append(type(n).__name__) or n,
    )
    assert "Program" in pre and "Identifier" in pre
    assert "Program" in post
    assert isinstance(result, Program)
    assert ASTOperations.traverse_node(None, lambda n: n, lambda n: n) is None
    assert ASTOperations.traverse_node(
        [Identifier(name="a")], lambda n: n, lambda n: n
    )[0].name == "a"


def test_ast_count_and_depth():
    tree = _fresh_tree()
    assert ASTOperations.count_nodes(None) == 0
    # 数据字段（如 name 字符串）也会被计入，故每个 Identifier 计 2
    assert ASTOperations.count_nodes([Identifier(name="a"), Identifier(name="b")]) == 4
    assert ASTOperations.count_nodes(tree) > 3
    assert ASTOperations.get_node_depth(None) == 0
    nested = Program(statements=[ExpressionStmt(expression=BinaryOp(
        left=Identifier(name="a"), operator="+", right=Identifier(name="b"),
    ))])
    assert ASTOperations.get_node_depth(nested) >= 3
    assert ASTOperations.get_node_depth([Identifier(name="a")]) >= 1


# ============================================================
# AST 内省接口（introspection.py）单元测试
# ============================================================

from dao.macros.introspection import ASTIntrospector
from dao.ast_nodes import (
    Assignment, FunctionCall, FunctionDecl, ClassDecl, IfStmt, WhileStmt,
    ForInStmt, ForRangeStmt, TryStmt, ReturnStmt, BreakStmt, ContinueStmt,
    ThrowStmt, AssertStmt, MacroDefinition, MacroCall, UnquoteExpr,
    SelectStmt, SelectCase, LogicBlock, LogicFact, LogicRule, LogicQuery,
    AsyncFunctionDecl, AwaitExpr, ChannelExpr, SendStmt, ReceiveExpr,
)


def build_introspection_program():
    return Program(statements=[
        VariableDecl(name="x", value=NumberLiteral(value=1)),
        VariableDecl(name="PI", value=NumberLiteral(value=3.14), is_constant=True),
        VariableDecl(name="标题", value=StringLiteral(value="你好")),
        FunctionDecl(name="helper", params=["a"], body=[
            ReturnStmt(value=BinaryOp(
                left=Identifier(name="a"), operator="+", right=NumberLiteral(value=1)
            )),
        ]),
        FunctionDecl(name="主函数", params=[], body=[
            ExpressionStmt(expression=FunctionCall(
                callee=Identifier(name="helper"), arguments=[Identifier(name="x")]
            )),
        ]),
        ClassDecl(name="人类", body=[]),
        IfStmt(condition=BooleanLiteral(value=True), body=[ExpressionStmt(Identifier(name="x"))],
               else_body=[BreakStmt()]),
        WhileStmt(condition=BooleanLiteral(value=True), body=[ContinueStmt()]),
        ForInStmt(variable="i", iterable=ListLiteral(elements=[NumberLiteral(value=1)]), body=[]),
        ForRangeStmt(variable="j", start=NumberLiteral(value=0), end=NumberLiteral(value=3), body=[]),
        TryStmt(try_body=[], catches=[], finally_body=[]),
        Assignment(target=Identifier(name="x"), value=NumberLiteral(value=2)),
        ThrowStmt(expression=Identifier(name="错误")),
        AssertStmt(condition=BooleanLiteral(value=True)),
        MacroDefinition(name="宏1", parameters=["p"], body=QuoteBlock(body=[])),
        MacroCall(name="宏1", arguments=[NumberLiteral(value=1)]),
        UnquoteExpr(expression=Identifier(name="x")),
        SelectStmt(cases=[SelectCase(type="timeout")]),
        LogicBlock(name="知识", facts=[LogicFact(predicate="父母", arguments=[])],
                   rules=[LogicRule()]),
        LogicQuery(knowledge_base="知识", goal=LogicFact(predicate="祖先", arguments=[])),
        AsyncFunctionDecl(name="异步任务", params=[], body=[]),
        AwaitExpr(expression=Identifier(name="异步任务")),
        ChannelExpr(capacity=2),
        SendStmt(channel=Identifier(name="ch"), value=NumberLiteral(value=1)),
        ReceiveExpr(channel=Identifier(name="ch")),
    ])


def test_introspector_basic_queries():
    insp = ASTIntrospector(build_introspection_program())
    assert insp.get_node_type() == "Program"
    assert insp.get_node_count() > 20
    assert insp.get_depth() >= 3
    assert len(insp.find_by_type(Identifier)) > 0


def test_introspector_expression_queries():
    insp = ASTIntrospector(build_introspection_program())
    assert len(insp.get_all_variables()) > 0
    assert len(insp.get_all_literals()) > 0
    assert len(insp.get_function_calls()) == 1
    assert len(insp.get_macro_calls()) == 1
    assert len(insp.get_quote_blocks()) == 1
    assert len(insp.get_unquote_exprs()) == 1


def test_introspector_statement_queries():
    insp = ASTIntrospector(build_introspection_program())
    assert len(insp.get_variable_definitions()) == 3
    assert len(insp.get_constant_definitions()) == 1
    assert len(insp.get_function_definitions()) == 2
    assert len(insp.get_macro_definitions()) == 1
    assert len(insp.get_class_definitions()) == 1


def test_introspector_control_flow_queries():
    insp = ASTIntrospector(build_introspection_program())
    assert len(insp.get_if_statements()) == 1
    assert len(insp.get_loop_statements()) == 3
    assert len(insp.get_try_statements()) == 1
    switches = insp.get_switch_statements()
    assert len(switches["matches"]) == 1 and len(switches["cases"]) == 1


def test_introspector_logic_and_concurrency_queries():
    insp = ASTIntrospector(build_introspection_program())
    assert len(insp.get_logic_blocks()) == 1
    assert len(insp.get_logic_queries()) == 1
    assert len(insp.get_logic_rules()) == 1
    assert len(insp.get_logic_facts()) >= 2
    assert len(insp.get_async_functions()) == 1
    assert len(insp.get_await_expressions()) == 1
    assert len(insp.get_channel_expressions()) == 1
    assert len(insp.get_send_receive_operations()) == 2


def test_introspector_advanced_analysis():
    insp = ASTIntrospector(build_introspection_program())
    usage = insp.get_variable_usage()
    assert "x" in usage and len(usage["x"]) >= 2
    assert isinstance(insp.get_free_variables(), set)
    deps = insp.get_function_dependencies()
    assert "helper" in deps
    cf = insp.analyze_control_flow()
    assert cf["if_count"] == 1 and cf["loop_count"] == 3
    assert cf["function_count"] == 2 and cf["macro_count"] == 1
    assert cf["break_count"] == 1 and cf["continue_count"] == 1
    assert cf["return_count"] == 1
    assert insp.has_side_effects() is True
    # 无副作用场景
    clean = ASTIntrospector(Program(statements=[ExpressionStmt(Identifier(name="x"))]))
    assert clean.has_side_effects() is False


def test_introspector_complexity_and_print(capsys):
    insp = ASTIntrospector(build_introspection_program())
    assert insp.calculate_cyclomatic_complexity() == 1 + 1 + 3 + 1
    mi = insp.calculate_maintainability_index()
    assert isinstance(mi, float) and 0 <= mi <= 100
    insp.print_statistics()
    insp.print_tree()
    captured = capsys.readouterr()
    assert "节点类型" in captured.out and "Program" in captured.out


# ============================================================
# 宏作用域管理（scope.py）单元测试
# ============================================================

from dao.macros.scope import VariableInfo, ScopeNode, MacroScope


def test_variable_info_and_scope_node():
    info = VariableInfo(name="x", is_bound=True, definition_line=3)
    info.add_use(5)
    info.add_use(5)
    assert info.used_lines == [5]
    node = ScopeNode(name="s", line=1)
    node.add_variable("x", is_bound=True, definition_line=3)
    node.add_variable("x")  # 重复添加不覆盖
    assert node.has_variable("x") is True and node.has_variable("y") is False
    assert node.get_variable("x").is_bound is True
    assert node.get_variable("y") is None
    assert node.lookup_variable("x") is not None
    child = ScopeNode(name="child")
    node.add_child(child)
    assert child.parent is node and node.children == [child]
    assert child.lookup_variable("x") is not None  # 沿作用域链向上查找


def test_macro_scope_basic():
    scope = MacroScope()
    assert scope.current is scope.root
    scope.enter_scope("s1")
    assert scope.current.name == "s1" and scope.current.parent is scope.root
    scope.define_variable("a", is_bound=True, line=5)
    assert scope.current.has_variable("a") is True
    scope.use_variable("a", line=6)
    assert scope.current.get_variable("a").used_lines == [6]
    scope.use_variable("free", line=7)  # 未定义变量视为自由变量
    assert scope.current.get_variable("free").definition_line == -1
    scope.leave_scope()
    assert scope.current is scope.root
    scope.leave_scope()  # 根作用域不可再离开
    assert scope.current is scope.root


def test_macro_scope_default_line():
    scope = MacroScope()
    scope.enter_scope()
    scope.define_variable("a")  # 默认行号
    scope.use_variable("a")
    assert scope.current.get_variable("a").used_lines != []


def test_macro_scope_used_and_free_variables():
    scope = MacroScope()
    scope.define_variable("bound", is_bound=True, line=1)
    scope.use_variable("bound", line=2)
    scope.use_variable("free", line=3)
    used = scope.get_used_variables()
    assert any(v.name == "bound" for v in used)
    free = scope.get_free_variables()
    assert any(v.name == "free" for v in free)
    assert str(scope).startswith("MacroScope")


def test_macro_scope_capture_analysis():
    scope = MacroScope()
    scope.use_variable("未知", line=1)
    captures = scope.analyze_captures()
    assert any(v.name == "未知" for v in captures)
    assert scope.analyze_capture_risk().get("未知") in ("中", "高")
    # 跨作用域引用 → 高风险
    scope2 = MacroScope()
    scope2.use_variable("共享", line=1)
    scope2.enter_scope()
    scope2.current.add_variable("共享", is_bound=False, definition_line=-1)
    scope2.use_variable("共享", line=2)
    assert scope2._count_scope_references("共享") == 2
    assert scope2.analyze_capture_risk().get("共享") == "高"


def test_macro_scope_unique_name_and_rewrite():
    scope = MacroScope()
    scope.define_variable("temp", is_bound=True)
    assert scope.generate_unique_name("temp") == "temp_1"
    scope.define_variable("temp_1", is_bound=True)
    assert scope.generate_unique_name("temp") == "temp_2"
    child = ScopeNode("child")
    scope.root.add_child(child)
    assert scope.generate_unique_name("new", child) == "new"
    scope.rewrite_variable("temp", "临时")
    assert scope.current.has_variable("临时") is True
    assert scope.current.has_variable("temp") is False


def test_macro_scope_apply_hygiene(capsys):
    scope = MacroScope()
    scope.use_variable("未知", line=1)
    mapping = scope.apply_hygiene()
    assert "未知" in mapping
    assert scope.current.has_variable(mapping["未知"]) is True
    scope.print_scope_tree()
    assert "作用域" in capsys.readouterr().out


# ============================================================
# 宏展开器（expander.py）单元测试
# ============================================================

from unittest.mock import MagicMock
from dao.macros.expander import MacroExpander
from dao.macros.registry import MacroRegistry
from dao.errors import 宏展开错误
from dao.ast_nodes import (
    FunctionCall, PatternBranch, PatternMatchBody, MatchStmt,
)


def test_expander_recursion_limit():
    ex = MacroExpander()
    ex.max_recursion = 0
    with pytest.raises(宏展开错误, match="递归深度超限"):
        ex.expand(Identifier(name="x"))


def test_expander_quote_block_and_unquote():
    ex = MacroExpander()
    block = QuoteBlock(body=[ExpressionStmt(expression=Identifier(name="x"))])
    out = ex.expand(block)
    assert isinstance(out, QuoteBlock) and out is not block
    assert out.body == block.body and out.body is not block.body
    # 注入表达式
    out = ex.expand(UnquoteExpr(expression=Identifier(name="x")))
    assert isinstance(out, Identifier) and out.name == "x"


def test_expander_other_nodes_dict_and_list():
    reg = MacroRegistry()
    reg.clear()
    reg.register_macro(MacroDefinition(
        name="M", parameters=[],
        body=QuoteBlock(body=[ExpressionStmt(expression=NumberLiteral(value=7))]),
    ))
    ex = MacroExpander(registry=reg)
    call = FunctionCall(
        callee=Identifier(name="f"),
        arguments=[MacroCall(name="M", arguments=[])],
        keyword_args={"k": MacroCall(name="M", arguments=[])},
    )
    out = ex.expand(call)
    assert isinstance(out.arguments[0], QuoteBlock)
    assert isinstance(out.keyword_args["k"], QuoteBlock)


def test_expander_parse_default_value():
    ex = MacroExpander()
    assert ex._parse_default_value("10", "x").value == 10
    assert ex._parse_default_value("-3", "x").value == -3
    assert ex._parse_default_value("3.14", "x").value == 3.14
    assert ex._parse_default_value("-3.14", "x").value == -3.14
    assert ex._parse_default_value("true", "x").value is True
    assert ex._parse_default_value("真", "x").value is True
    assert ex._parse_default_value("false", "x").value is False
    assert ex._parse_default_value("假", "x").value is False
    assert isinstance(ex._parse_default_value("null", "x"), NullLiteral)
    assert isinstance(ex._parse_default_value("空", "x"), NullLiteral)
    assert ex._parse_default_value('"abc"', "x").value == "abc"
    assert ex._parse_default_value("'abc'", "x").value == "abc"
    assert ex._parse_default_value("任意", "块") is None
    assert ex._parse_default_value("任意", "x").value == 0
    assert ex._parse_default_value(None, "x") is None


def test_expander_apply_macro_parameters_and_replace():
    ex = MacroExpander()
    body = [ReturnStmt(value=BinaryOp(
        left=Identifier(name="x"), operator="+", right=Identifier(name="y")
    ))]
    out = ex._apply_macro_parameters(
        body, ["x", "y"], [NumberLiteral(value=1), NumberLiteral(value=2)]
    )
    assert isinstance(out, BinaryOp) and out.left.value == 1 and out.right.value == 2
    replacements = {"x": NumberLiteral(value=9)}
    assert ex._replace_in_node([Identifier(name="x")], replacements)[0].value == 9
    assert ex._replace_in_node((Identifier(name="x"),), replacements)[0].value == 9
    assert ex._replace_in_node({"a": Identifier(name="x")}, replacements)["a"].value == 9
    assert ex._replace_in_node(None, replacements) is None
    u = UnquoteExpr(expression=BinaryOp(
        left=Identifier(name="x"), operator="+", right=NumberLiteral(value=1)
    ))
    assert ex._replace_in_node(u, replacements).expression.left.value == 9
    q = QuoteBlock(body=[ExpressionStmt(expression=Identifier(name="x"))])
    assert ex._replace_in_node(q, replacements).body[0].expression.value == 9
    node = Identifier(name="x")
    assert ex._replace_in_node(node, {}) is node


def test_expander_error_modes():
    reg = MacroRegistry()
    reg.clear()
    call = MacroCall(name="失败", arguments=[Identifier(name="x")], line=3, column=4)
    ex = MacroExpander(registry=reg)
    # 未找到宏 → 原样返回
    assert ex.expand(call) is call
    # 模拟查找宏时抛异常
    ex.registry.find_macro = MagicMock(side_effect=ValueError("boom"))
    ex.error_mode = MacroExpander.PERMISSIVE
    assert ex.expand(call) is call
    assert len(ex.expansion_errors) == 1
    assert ex.expansion_errors[0]["macro_name"] == "失败"
    assert ex.expansion_errors[0]["line"] == 3
    ex.error_mode = MacroExpander.STRICT
    with pytest.raises(宏展开错误, match="展开失败"):
        ex.expand(call)


def test_expander_trace_and_stack():
    ex = MacroExpander()
    assert ex.get_trace_log() is None
    assert ex.format_call_stack() == "宏调用栈为空"
    ex.set_trace(True)
    assert ex.get_trace_log() == []
    ex._log_trace("开始", "M", "详情")
    assert ex.get_trace_log()[0]["phase"] == "开始"
    ex._call_stack.append({"name": "M", "line": 1, "column": 2, "depth": 0})
    stack_str = ex.format_call_stack()
    assert "!M" in stack_str and "行 1" in stack_str
    assert len(ex.get_call_stack()) == 1
    ex._call_stack.clear()
    ex.set_trace(False)
    assert ex.get_trace_log() is None


def test_expander_ast_diff_and_misc():
    ex = MacroExpander()
    assert "无变化" in ex.ast_diff(Identifier(name="a"), Identifier(name="a"))[0]
    assert any("展开前" in d for d in ex.ast_diff(Identifier(name="a"), Identifier(name="b")))
    assert "无变化" in ex.ast_diff(NumberLiteral(value=1), NumberLiteral(value=1))[0]
    assert "无变化" in ex.ast_diff([Identifier(name="a")], [Identifier(name="a")])[0]
    assert "无变化" in ex.ast_diff(None, None)[0]
    assert "MacroExpander" in repr(ex)
    ex.register_builtin_macros()
    assert ex.registry.find_macro("除非") is not None


def test_expander_pattern_macro_expansion():
    reg = MacroRegistry()
    reg.clear()
    branch = PatternBranch(
        pattern=Identifier(name="_"),
        body=QuoteBlock(body=[ExpressionStmt(expression=StringLiteral(value="通配"))]),
    )
    reg.register_macro(MacroDefinition(
        name="描述", parameters=["值"], body=PatternMatchBody(branches=[branch])
    ))
    ex = MacroExpander(registry=reg)
    out = ex.expand(MacroCall(name="描述", arguments=[NumberLiteral(value=5)]))
    assert isinstance(out, list)
    assert isinstance(out[0], VariableDecl)
    assert isinstance(out[-1], MatchStmt)
    assert out[-1].subject.name == "值"
    assert len(out[-1].cases) == 1
    assert out[-1].cases[0].is_wildcard is True

# ============================================================
# 宏块注入：列表作为整体表达式代入（回归测试）
# ============================================================


def test_macro_block_list_injection():
    """宏块参数是列表时应整体注入，不能只取最后一个元素"""
    code = """
定义宏 取值(块)
    返回 引述
        定义 x = $块
        x
定义 r = !取值()
    [1, 2, 3]
"""
    result, interpreter = run_code(code)
    assert interpreter.global_env.get("r") == [1, 2, 3]


def test_macro_block_nested_list_injection():
    """嵌套列表同样应整体注入"""
    code = """
定义宏 取值(块)
    返回 引述
        定义 x = $块
        x
定义 r = !取值()
    [[1, 2], [3, 4]]
"""
    result, interpreter = run_code(code)
    assert interpreter.global_env.get("r") == [[1, 2], [3, 4]]


def test_macro_block_scalar_and_expression_injection():
    """标量与单个表达式注入不受影响"""
    code = """
定义宏 取值(块)
    返回 引述
        定义 x = $块
        x
定义 a = !取值()
    42
定义 b = !取值()
    2 + 3
"""
    result, interpreter = run_code(code)
    assert interpreter.global_env.get("a") == 42
    assert interpreter.global_env.get("b") == 5


def test_macro_block_dict_injection():
    """字典注入不受影响，且其中的列表保持完整"""
    code = """
定义宏 取值(块)
    返回 引述
        定义 x = $块
        x
定义 r = !取值()
    {"键": [1, 2, 3]}
"""
    result, interpreter = run_code(code)
    assert interpreter.global_env.get("r") == {"键": [1, 2, 3]}


def test_macro_block_result_assignment():
    """真实场景：宏块内 定义 __结果 = $代码块 产出列表"""
    code = """
定义宏 包裹(代码块)
    返回 引述
        定义 __结果 = $代码块
        __结果
定义 r = !包裹()
    [7, 8, 9]
"""
    result, interpreter = run_code(code)
    assert interpreter.global_env.get("r") == [7, 8, 9]
