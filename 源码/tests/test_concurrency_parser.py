"""
并发编程测试
============

覆盖：并发类型（Channel, BufferedChannel, Mutex, AtomicInt, AtomicBool）、
      解析器（异步函数、等待、并行、通道、选择器、同步块）
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from dao.lexer import Lexer
from dao.parser import Parser
from dao.interpreter import Interpreter
from dao.concurrency import Channel, BufferedChannel, Mutex, AtomicInt, AtomicBool
from dao.errors import 运行时错误


def parse(source: str):
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse()


def run(source: str) -> object:
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    interpreter = Interpreter()
    return interpreter.execute(ast)


def capture_output(source: str) -> str:
    import io
    from contextlib import redirect_stdout
    f = io.StringIO()
    with redirect_stdout(f):
        run(source)
    return f.getvalue()


# ============================================================
# 并发类型单元测试
# ============================================================

class TestChannel:
    """无缓冲通道测试"""

    def test_send_and_receive(self):
        ch = Channel()
        ch.send(42)
        assert ch.receive() == 42

    def test_close_channel(self):
        ch = Channel()
        ch.send(1)
        ch.close()
        assert ch.closed is True

    def test_send_to_closed_channel(self):
        ch = Channel()
        ch.close()
        with pytest.raises(运行时错误):
            ch.send(1)

    def test_receive_from_closed_empty_channel(self):
        ch = Channel()
        ch.close()
        with pytest.raises(StopIteration):
            ch.receive()


class TestBufferedChannel:
    """缓冲通道测试"""

    def test_buffered_send_and_receive(self):
        ch = BufferedChannel(3)
        ch.send(10)
        ch.send(20)
        ch.send(30)
        assert ch.receive() == 10
        assert ch.receive() == 20
        assert ch.receive() == 30

    def test_buffered_close(self):
        ch = BufferedChannel(2)
        ch.send(1)
        ch.close()
        assert ch.closed is True
        assert ch.receive() == 1

    def test_send_to_closed_buffered(self):
        ch = BufferedChannel(2)
        ch.close()
        with pytest.raises(运行时错误):
            ch.send(1)


class TestMutex:
    """互斥锁测试"""

    def test_acquire_and_release(self):
        m = Mutex()
        m.acquire()
        m.release()

    def test_context_manager(self):
        m = Mutex()
        with m:
            pass

    def test_mutex_protects_shared_state(self):
        import threading
        m = Mutex()
        counter = [0]

        def increment():
            for _ in range(100):
                with m:
                    counter[0] += 1

        threads = [threading.Thread(target=increment) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert counter[0] == 500


class TestAtomicInt:
    """原子整数测试"""

    def test_get_and_set(self):
        a = AtomicInt(10)
        assert a.get() == 10
        a.set(20)
        assert a.get() == 20

    def test_add(self):
        a = AtomicInt(0)
        assert a.add(5) == 5
        assert a.add(3) == 8

    def test_compare_and_set_success(self):
        a = AtomicInt(10)
        assert a.compare_and_set(10, 20) is True
        assert a.get() == 20

    def test_compare_and_set_failure(self):
        a = AtomicInt(10)
        assert a.compare_and_set(5, 20) is False
        assert a.get() == 10

    def test_thread_safety(self):
        import threading
        a = AtomicInt(0)

        def increment():
            for _ in range(1000):
                a.add(1)

        threads = [threading.Thread(target=increment) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert a.get() == 5000


class TestAtomicBool:
    """原子布尔测试"""

    def test_get_and_set(self):
        a = AtomicBool(False)
        assert a.get() is False
        a.set(True)
        assert a.get() is True

    def test_toggle(self):
        a = AtomicBool(False)
        assert a.toggle() is True
        assert a.toggle() is False

    def test_compare_and_set(self):
        a = AtomicBool(False)
        assert a.compare_and_set(False, True) is True
        assert a.compare_and_set(False, True) is False


# ============================================================
# 解析器测试
# ============================================================

class TestConcurrencyParser:
    """并发语法解析测试"""

    def test_parse_async_function(self):
        source = '异步 函数 获取数据()\n    返回 42\n'
        ast = parse(source)
        assert len(ast.statements) == 1
        stmt = ast.statements[0]
        assert stmt.__class__.__name__ == 'AsyncFunctionDecl'
        assert stmt.name == '获取数据'

    def test_parse_async_function_with_params(self):
        source = '异步 函数 请求(网址, 超时)\n    返回 网址\n'
        ast = parse(source)
        stmt = ast.statements[0]
        assert stmt.name == '请求'
        assert stmt.params == ['网址', '超时']

    def test_parse_parallel_stmt(self):
        source = '并行\n    打印("hello")\n'
        ast = parse(source)
        assert len(ast.statements) == 1
        stmt = ast.statements[0]
        assert stmt.__class__.__name__ == 'ParallelStmt'

    def test_parse_channel_expr(self):
        source = '定义 ch = 通道()\n'
        ast = parse(source)
        assert len(ast.statements) == 1

    def test_parse_channel_with_capacity(self):
        source = '定义 ch = 通道(3)\n'
        ast = parse(source)
        assert len(ast.statements) == 1

    def test_parse_sync_stmt(self):
        source = '定义 锁 = 互斥锁()\n同步 锁\n    打印("受保护")\n'
        ast = parse(source)
        assert len(ast.statements) == 2
        assert ast.statements[1].__class__.__name__ == 'SyncStmt'

    def test_parse_select_stmt_with_case(self):
        source = (
            '定义 ch = 通道()\n'
            '选择\n'
            '    情况 接收 ch 作为 数据:\n'
            '        打印(数据)\n'
        )
        ast = parse(source)
        assert len(ast.statements) == 2
        assert ast.statements[1].__class__.__name__ == 'SelectStmt'


# ============================================================
# 解释器集成测试
# ============================================================

class TestConcurrencyInterpreter:
    """并发解释执行测试"""

    def test_mutex_builtin(self):
        source = '定义 锁 = 互斥锁()\n打印(锁)\n'
        output = capture_output(source)
        assert 'Mutex' in output or '互斥锁' in output or len(output.strip()) > 0

    def test_atomic_int_builtin(self):
        source = (
            '定义 计数器 = 原子整数(0)\n'
            '计数器.加(10)\n'
            '打印(计数器.获取())\n'
        )
        output = capture_output(source)
        assert output.strip() == '10'

    def test_atomic_int_add_and_get(self):
        source = (
            '定义 计数器 = 原子整数(5)\n'
            '计数器.加(3)\n'
            '打印(计数器.获取())\n'
        )
        output = capture_output(source)
        assert output.strip() == '8'

    def test_atomic_bool_builtin(self):
        source = (
            '定义 标志 = 原子布尔(假)\n'
            '标志.设置(真)\n'
            '打印(标志.获取())\n'
        )
        output = capture_output(source)
        assert output.strip() == '真'

    def test_channel_create_and_send_receive(self):
        source = (
            '定义 ch = 通道()\n'
            'ch.发送(42)\n'
            '定义 值 = ch.接收()\n'
            '打印(值)\n'
        )
        output = capture_output(source)
        assert output.strip() == '42'

    def test_buffered_channel(self):
        source = (
            '定义 ch = 通道(3)\n'
            'ch.发送(1)\n'
            'ch.发送(2)\n'
            'ch.发送(3)\n'
            '打印(ch.接收())\n'
            '打印(ch.接收())\n'
            '打印(ch.接收())\n'
        )
        output = capture_output(source)
        lines = output.strip().split('\n')
        assert lines == ['1', '2', '3']

    def test_channel_close(self):
        source = (
            '定义 ch = 通道()\n'
            'ch.发送(99)\n'
            'ch.关闭()\n'
            '打印(ch.已关闭)\n'
        )
        output = capture_output(source)
        assert output.strip() == '真'

    def test_mutex_sync_block(self):
        source = (
            '定义 锁 = 互斥锁()\n'
            '定义 计数器 = 0\n'
            '同步 锁\n'
            '    计数器 = 计数器 + 1\n'
            '打印(计数器)\n'
        )
        output = capture_output(source)
        assert output.strip() == '1'

    def test_atomic_int_compare_and_set(self):
        source = (
            '定义 计数器 = 原子整数(10)\n'
            '定义 结果 = 计数器.比较并设置(10, 20)\n'
            '打印(结果)\n'
            '打印(计数器.获取())\n'
        )
        output = capture_output(source)
        lines = output.strip().split('\n')
        assert lines[0] == '真'
        assert lines[1] == '20'

    def test_parallel_block_with_channel(self):
        source = (
            '定义 ch = 通道(5)\n'
            '并行\n'
            '    ch.发送(1)\n'
            '    ch.发送(2)\n'
            '    ch.发送(3)\n'
            '定义 a = ch.接收()\n'
            '定义 b = ch.接收()\n'
            '定义 c = ch.接收()\n'
            '打印(a + b + c)\n'
        )
        output = capture_output(source)
        assert output.strip() == '6'

    def test_parallel_block_with_atomic(self):
        source = (
            '定义 计数器 = 原子整数(0)\n'
            '并行\n'
            '    计数器.加(10)\n'
            '    计数器.加(20)\n'
            '打印(计数器.获取())\n'
        )
        output = capture_output(source)
        assert output.strip() == '30'


# ============================================================
# 并发解析器分支补测
# ============================================================

class TestConcurrencyParserBranches:
    """覆盖并发解析器的修饰符、等待表达式与选择语句各语法变体"""

    @staticmethod
    def _find(node, node_type):
        """在 AST 中递归查找指定类型的节点"""
        if isinstance(node, node_type):
            return node
        for attr in ("expression", "channel", "value", "mutex", "condition",
                     "timeout_value", "target"):
            child = getattr(node, attr, None)
            if child is not None and hasattr(child, "__class__"):
                found = TestConcurrencyParserBranches._find(child, node_type)
                if found is not None:
                    return found
        for attr in ("statements", "body", "expressions", "elements", "cases"):
            children = getattr(node, attr, None)
            if isinstance(children, list):
                for child in children:
                    found = TestConcurrencyParserBranches._find(child, node_type)
                    if found is not None:
                        return found
        return None

    def test_async_function_modifiers(self):
        ast = parse('异步 静态 私有 函数 取数()\n    返回 1\n')
        stmt = ast.statements[0]
        assert stmt.__class__.__name__ == 'AsyncFunctionDecl'
        assert stmt.is_static is True
        assert stmt.is_private is True

    def test_async_function_skips_blank_lines(self):
        ast = parse('异步 函数 取数()\n\n\n    返回 1\n')
        assert ast.statements[0].__class__.__name__ == 'AsyncFunctionDecl'

    def test_await_expr(self):
        from dao.ast_nodes import AwaitExpr
        ast = parse('定义 结果 = 等待 取值()\n')
        assert self._find(ast, AwaitExpr) is not None

    def test_await_all_expr(self):
        from dao.ast_nodes import AwaitAllExpr
        ast = parse('定义 结果 = 全部(取值(), 另一个())\n')
        node = self._find(ast, AwaitAllExpr)
        assert node is not None
        assert len(node.expressions) == 2

    def test_await_race_expr(self):
        from dao.ast_nodes import AwaitRaceExpr
        ast = parse('定义 结果 = 竞速(取值(), 另一个(), 第三个())\n')
        node = self._find(ast, AwaitRaceExpr)
        assert node is not None
        assert len(node.expressions) == 3

    def test_send_stmt_with_comma(self):
        ast = parse('发送 ch, 42\n')
        assert ast.statements[0].__class__.__name__ == 'SendStmt'

    def test_receive_expr(self):
        from dao.ast_nodes import ReceiveExpr
        ast = parse('定义 值 = 接收 ch\n')
        assert self._find(ast, ReceiveExpr) is not None

    def test_select_dang_condition_case(self):
        ast = parse('选择\n    当 真\n        打印("ok")\n')
        stmt = ast.statements[0]
        assert stmt.cases[0].type == 'condition'
        assert getattr(stmt.cases[0], 'condition', None) is not None

    def test_select_dang_receive_case(self):
        ast = parse('选择\n    当 值 = 接收 ch\n        打印(值)\n')
        case = ast.statements[0].cases[0]
        assert case.type == 'receive'
        assert case.variable == '值'

    def test_select_dang_timeout_case(self):
        ast = parse('选择\n    当 超时(0.1)\n        打印("超时")\n')
        case = ast.statements[0].cases[0]
        assert case.type == 'timeout'
        assert case.timeout_value is not None

    def test_select_default_case(self):
        ast = parse('选择\n    默认\n        打印("默认")\n')
        case = ast.statements[0].cases[0]
        assert case.type == 'timeout'
        assert case.timeout_value is None

    def test_select_braces_syntax(self):
        ast = parse('选择 {\n    情况 接收 ch 作为 值:\n        打印(值)\n}\n')
        case = ast.statements[0].cases[0]
        assert case.type == 'receive'
        assert case.variable == '值'

    def test_select_case_timeout(self):
        ast = parse('选择\n    情况 超时(0.1):\n        打印("超时")\n')
        case = ast.statements[0].cases[0]
        assert case.type == 'timeout'
        assert len(case.body) >= 1

    def test_select_case_single_statement_body(self):
        ast = parse('选择\n    情况 接收 ch 作为 值: 打印(值)\n')
        case = ast.statements[0].cases[0]
        assert len(case.body) == 1

    def test_select_invalid_branch_raises(self):
        from dao.errors import 语法错误
        with pytest.raises(语法错误):
            parse('选择\n    打印("x")\n')

    def test_select_invalid_case_type_raises(self):
        from dao.errors import 语法错误
        with pytest.raises(语法错误):
            parse('选择\n    情况 真: 打印(1)\n')

    def test_parse_param_list_directly(self):
        from dao.ast_nodes import NumberLiteral
        from dao.parser.modules.concurrency import ConcurrencyParser
        parser = Parser(Lexer('a, b = 2)').tokenize())
        params, defaults = ConcurrencyParser._parse_param_list(parser)
        assert params == ['a', 'b']
        assert isinstance(defaults['b'], NumberLiteral)
        assert defaults['b'].value == 2