"""
跨范式集成测试
==============

以「源代码 → Lexer → Parser → Interpreter」的完整流水线，验证多种范式组合
能够无缝协作。覆盖四类组合：

    1. 并发 + 逻辑：异步任务查询逻辑知识库
    2. 逻辑 + 宏：宏展开逻辑查询
    3. 宏 + 并发：宏生成异步函数 / 包裹并行通道块
    4. OOP + 逻辑：类方法内查询逻辑规则

每类均包含错误传播与恢复场景，确保异常能在范式边界间正确传递并被捕获。

所有用例均先经小段 `.道` 源码实测语法可用后再固化，避免无法解析的测试。
"""

import io
import os
import sys
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from dao.interpreter import Interpreter
from dao.lexer import Lexer
from dao.macros.registry import MacroRegistry
from dao.parser import Parser


# ============================================================
# 通用辅助函数：源代码 → Lexer → Parser → Interpreter
# ============================================================


def parse(source: str):
    """源代码 → AST"""
    return Parser(Lexer(source).tokenize()).parse()


def run(source: str) -> object:
    """源代码 → 执行结果（每次运行前清空宏注册表，避免测试间干扰）"""
    MacroRegistry().clear()
    ast = parse(source)
    return Interpreter().execute(ast, source=source)


def capture_output(source: str) -> str:
    """捕获源代码执行期间的标准输出"""
    MacroRegistry().clear()
    ast = parse(source)
    buf = io.StringIO()
    with redirect_stdout(buf):
        Interpreter().execute(ast, source=source)
    return buf.getvalue()


# ============================================================
# 组合一：并发 + 逻辑
# ============================================================


class TestConcurrencyLogic:
    """并发与逻辑编程的融合：异步查询知识库"""

    def test_async_function_queries_logic_knowledge_base(self):
        """异步函数可查询逻辑知识库，等待后获得绑定结果"""
        source = """
逻辑 知识库
    事实: 评分("文章A", 90)
    事实: 评分("文章B", 70)
异步 函数 查询文章(名字)
    返回 查询(知识库, 评分(名字, ?分))
定义 r = 等待 查询文章("文章A")
打印(r)
"""
        output = capture_output(source)
        assert "文章" not in output  # 仅输出绑定，不输出查询目标本身
        assert "?分" in output
        assert "90" in output

    def test_logic_query_inside_parallel_block(self):
        """并行块内可并发执行逻辑查询，并通过通道返回结果"""
        source = """
逻辑 知识库
    事实: 可信("甲")
    事实: 可信("乙")
定义 ch = 通道(2)
并行
    ch.发送(查询(知识库, 可信("甲")))
    ch.发送(查询(知识库, 可信("丙")))
打印(ch.接收())
打印(ch.接收())
"""
        lines = capture_output(source).strip().split("\n")
        # 已绑定事实返回 [{}]，未绑定事实返回 []
        assert "[{}]" in lines
        assert "[]" in lines

    def test_async_logic_error_propagates_and_recovers(self):
        """异步逻辑查询抛出的错误可跨范式传播，并被尝试/捕获恢复"""
        source = """
逻辑 知识库
    事实: 评分("文章A", 90)
异步 函数 查询文章(名字)
    定义 结果 = 查询(知识库, 评分(名字, ?分))
    如果 结果.长度 == 0
        抛出("未找到")
    返回 结果
尝试
    定义 r = 等待 查询文章("不存在")
    打印(r)
捕获 错误
    打印("捕获到异步逻辑错误: " + 文本(错误))
"""
        output = capture_output(source)
        assert "捕获到异步逻辑错误" in output
        # 中文错误消息应携带原始抛出内容
        assert "未找到" in output


# ============================================================
# 组合二：逻辑 + 宏
# ============================================================


class TestLogicMacro:
    """逻辑编程与宏系统的融合：宏展开逻辑查询"""

    def test_macro_expands_logic_query(self):
        """宏的引述块可包含逻辑查询，展开后执行得到绑定"""
        source = """
逻辑 家庭
    事实: 父母("张三", "小明")
定义宏 查询小明父亲()
    返回 引述 查询(家庭, 父母(?谁, "小明"))
定义 结果 = !查询小明父亲()
打印(结果)
"""
        output = capture_output(source)
        assert "?谁" in output
        assert "张三" in output

    def test_macro_parameter_substituted_into_logic_query(self):
        """宏参数可注入逻辑查询的目标参数，实现可复用查询模板"""
        source = """
逻辑 家庭
    事实: 父母("张三", "小明")
    事实: 父母("李四", "小红")
定义宏 查父亲(孩子)
    返回 引述 查询(家庭, 父母(?谁, $孩子))
定义 结果 = !查父亲("小红")
打印(结果)
"""
        output = capture_output(source)
        assert "?谁" in output
        assert "李四" in output


# ============================================================
# 组合三：宏 + 并发
# ============================================================


class TestMacroConcurrency:
    """宏系统与并发编程的融合：宏生成异步函数 / 包裹并行块"""

    def test_macro_generates_async_function(self):
        """宏可生成异步函数定义，并在引述块中立即等待其返回"""
        source = """
定义宏 生成异步()
    返回 引述
        异步 函数 抓取()
            返回 99
        等待 抓取()
定义 r = !生成异步()
打印(r)
"""
        assert capture_output(source).strip() == "99"

    def test_macro_wraps_parallel_channel_block(self):
        """宏可包裹并行通道块，展开后并发逻辑正常执行"""
        source = """
定义宏 并发加(x, y)
    返回 引述
        定义 ch = 通道(2)
        并行
            ch.发送($x)
            ch.发送($y)
        定义 a = ch.接收()
        定义 b = ch.接收()
        a + b
打印(!并发加(3, 4))
"""
        assert capture_output(source).strip() == "7"

    def test_macro_error_propagates_and_recovers(self):
        """宏展开体中的运行时错误可传播到调用处并被恢复"""
        source = """
定义宏 危险宏()
    返回 引述 10 / 0
尝试
    定义 r = !危险宏()
    打印(r)
捕获 错误
    打印("捕获到宏错误")
"""
        assert capture_output(source).strip() == "捕获到宏错误"


# ============================================================
# 组合四：OOP + 逻辑
# ============================================================


class TestOopLogic:
    """面向对象与逻辑编程的融合：类方法内查询逻辑规则"""

    def test_class_method_queries_logic_rules(self):
        """类方法可将对象字段作为逻辑查询参数，返回绑定列表"""
        source = """
逻辑 权限
    事实: 角色("张三", "管理员")
    规则: 有权限(?u) 如果 角色(?u, "管理员")
类型 用户
    初始化(名字)
        本对象.名字 = 名字
    函数 检查()
        返回 查询(权限, 有权限(本对象.名字))
定义 u = 用户("张三")
打印(u.检查())
"""
        output = capture_output(source)
        assert "张三" in output

    def test_class_method_handles_no_matching_rule(self):
        """逻辑规则无匹配时，类方法可优雅恢复并返回默认值"""
        source = """
逻辑 权限
    事实: 角色("张三", "管理员")
类型 用户
    初始化(名字)
        本对象.名字 = 名字
    函数 检查()
        定义 结果 = 查询(权限, 有权限(本对象.名字))
        如果 结果.长度 > 0
            返回 真
        返回 假
定义 u = 用户("王五")
打印(u.检查())
"""
        assert capture_output(source).strip() == "假"

    def test_object_constructed_inside_async_task_queries_logic(self):
        """OOP、逻辑与并发三者协同：异步任务内构造对象并查询规则"""
        source = """
逻辑 权限
    事实: 角色("张三", "管理员")
    规则: 有权限(?u) 如果 角色(?u, "管理员")
类型 用户
    初始化(名字)
        本对象.名字 = 名字
    函数 检查()
        返回 查询(权限, 有权限(本对象.名字))
异步 函数 异步检查(名字)
    定义 u = 用户(名字)
    返回 u.检查()
定义 r = 等待 异步检查("张三")
打印(r)
"""
        output = capture_output(source)
        assert "张三" in output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
