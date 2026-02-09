"""
新特性综合测试
=============

覆盖：OOP、高阶函数、管道运算符、成员运算符、模式匹配
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from dao.lexer import Lexer
from dao.parser import Parser
from dao.interpreter import Interpreter
from dao.errors import 运行时错误, 名称错误


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
# OOP: 类型系统
# ============================================================

class TestOOPBasics:
    """面向对象基础测试"""

    def test_class_definition_and_instantiation(self):
        source = (
            '类型 动物\n'
            '    初始化(名字)\n'
            '        本对象.名字 = 名字\n'
            '定义 猫 = 动物("咪咪")\n'
            '打印(猫.名字)\n'
        )
        output = capture_output(source)
        assert output.strip() == "咪咪"

    def test_method_call(self):
        source = (
            '类型 计算器\n'
            '    初始化()\n'
            '        本对象.结果 = 0\n'
            '    函数 加(数值)\n'
            '        本对象.结果 = 本对象.结果 + 数值\n'
            '        返回 本对象\n'
            '    函数 获取结果()\n'
            '        返回 本对象.结果\n'
            '定义 计 = 计算器()\n'
            '计.加(10)\n'
            '计.加(20)\n'
            '打印(计.获取结果())\n'
        )
        output = capture_output(source)
        assert output.strip() == "30"

    def test_inheritance(self):
        source = (
            '类型 动物\n'
            '    初始化(名字)\n'
            '        本对象.名字 = 名字\n'
            '    函数 说话()\n'
            '        返回 "..."\n'
            '类型 猫 继承自 动物\n'
            '    初始化(名字)\n'
            '        父对象.初始化(名字)\n'
            '    函数 说话()\n'
            '        返回 本对象.名字 + " 说: 喵~"\n'
            '定义 小猫 = 猫("咪咪")\n'
            '打印(小猫.说话())\n'
        )
        output = capture_output(source)
        assert output.strip() == "咪咪 说: 喵~"

    def test_polymorphism(self):
        source = (
            '类型 形状\n'
            '    初始化()\n'
            '        本对象.类别 = "形状"\n'
            '    函数 面积()\n'
            '        返回 0\n'
            '类型 圆形 继承自 形状\n'
            '    初始化(半径)\n'
            '        父对象.初始化()\n'
            '        本对象.半径 = 半径\n'
            '    函数 面积()\n'
            '        返回 3.14 * 本对象.半径 ** 2\n'
            '类型 矩形 继承自 形状\n'
            '    初始化(宽, 高)\n'
            '        父对象.初始化()\n'
            '        本对象.宽 = 宽\n'
            '        本对象.高 = 高\n'
            '    函数 面积()\n'
            '        返回 本对象.宽 * 本对象.高\n'
            '定义 形状列表 = [圆形(5), 矩形(3, 4)]\n'
            '遍历 s 在 形状列表\n'
            '    打印(s.面积())\n'
        )
        output = capture_output(source)
        lines = output.strip().split('\n')
        assert float(lines[0]) == pytest.approx(78.5)
        assert float(lines[1]) == 12

    def test_inherited_method(self):
        """子类应继承父类的方法"""
        source = (
            '类型 基类\n'
            '    初始化()\n'
            '        本对象.值 = 42\n'
            '    函数 获取值()\n'
            '        返回 本对象.值\n'
            '类型 子类 继承自 基类\n'
            '    初始化()\n'
            '        父对象.初始化()\n'
            '定义 实例 = 子类()\n'
            '打印(实例.获取值())\n'
        )
        output = capture_output(source)
        assert output.strip() == "42"

    def test_field_modification(self):
        source = (
            '类型 盒子\n'
            '    初始化(内容)\n'
            '        本对象.内容 = 内容\n'
            '定义 盒 = 盒子("苹果")\n'
            '打印(盒.内容)\n'
            '盒.内容 = "香蕉"\n'
            '打印(盒.内容)\n'
        )
        output = capture_output(source)
        assert output.strip() == "苹果\n香蕉"

    def test_is_instance(self):
        source = (
            '类型 动物\n'
            '    初始化()\n'
            '        本对象.名 = "动物"\n'
            '类型 猫 继承自 动物\n'
            '    初始化()\n'
            '        父对象.初始化()\n'
            '定义 小猫 = 猫()\n'
            '打印(是实例(小猫, 猫))\n'
            '打印(是实例(小猫, 动物))\n'
        )
        output = capture_output(source)
        assert output.strip() == "真\n真"


# ============================================================
# 高阶函数
# ============================================================

class TestHigherOrderFunctions:
    """高阶函数测试"""

    def test_映射(self):
        source = (
            '定义 数列 = [1, 2, 3, 4, 5]\n'
            '定义 结果 = 映射(数列, 函数(x) => x * 2)\n'
            '打印(结果)\n'
        )
        output = capture_output(source)
        assert output.strip() == "[2, 4, 6, 8, 10]"

    def test_筛选(self):
        source = (
            '定义 数列 = [1, 2, 3, 4, 5, 6]\n'
            '定义 结果 = 筛选(数列, 函数(x) => x % 2 == 0)\n'
            '打印(结果)\n'
        )
        output = capture_output(source)
        assert output.strip() == "[2, 4, 6]"

    def test_折叠(self):
        source = (
            '定义 数列 = [1, 2, 3, 4, 5]\n'
            '定义 总和 = 折叠(数列, 0, 函数(累计, 当前) => 累计 + 当前)\n'
            '打印(总和)\n'
        )
        output = capture_output(source)
        assert output.strip() == "15"

    def test_排序(self):
        source = (
            '定义 数列 = [3, 1, 4, 1, 5, 9, 2, 6]\n'
            '定义 结果 = 排序(数列)\n'
            '打印(结果)\n'
        )
        output = capture_output(source)
        assert output.strip() == "[1, 1, 2, 3, 4, 5, 6, 9]"

    def test_排序_降序(self):
        source = (
            '定义 数列 = [3, 1, 4, 1, 5]\n'
            '定义 结果 = 排序(数列, 降序=真)\n'
            '打印(结果)\n'
        )
        output = capture_output(source)
        assert output.strip() == "[5, 4, 3, 1, 1]"

    def test_排序_自定义键(self):
        source = (
            '定义 数列 = ["苹果", "梨", "香蕉西瓜", "橙"]\n'
            '定义 结果 = 排序(数列, 键=函数(x) => 长度(x))\n'
            '打印(结果)\n'
        )
        output = capture_output(source)
        assert output.strip() == "['梨', '橙', '苹果', '香蕉西瓜']"

    def test_每个满足(self):
        source = (
            '定义 数列 = [2, 4, 6, 8]\n'
            '打印(每个满足(数列, 函数(x) => x % 2 == 0))\n'
        )
        output = capture_output(source)
        assert output.strip() == "真"

    def test_存在满足(self):
        source = (
            '定义 数列 = [1, 3, 5, 6]\n'
            '打印(存在满足(数列, 函数(x) => x % 2 == 0))\n'
        )
        output = capture_output(source)
        assert output.strip() == "真"

    def test_查找(self):
        source = (
            '定义 数列 = [1, 2, 3, 4, 5]\n'
            '定义 结果 = 查找(数列, 函数(x) => x > 3)\n'
            '打印(结果)\n'
        )
        output = capture_output(source)
        assert output.strip() == "4"

    def test_展平映射(self):
        source = (
            '定义 数列 = [1, 2, 3]\n'
            '定义 结果 = 展平映射(数列, 函数(x) => [x, x * 10])\n'
            '打印(结果)\n'
        )
        output = capture_output(source)
        assert output.strip() == "[1, 10, 2, 20, 3, 30]"


# ============================================================
# 管道运算符
# ============================================================

class TestPipeOperator:
    """管道运算符测试"""

    def test_simple_pipe(self):
        source = (
            '定义 数列 = [3, 1, 4, 1, 5]\n'
            '定义 结果 = 数列 |> 排序()\n'
            '打印(结果)\n'
        )
        output = capture_output(source)
        assert output.strip() == "[1, 1, 3, 4, 5]"

    def test_pipe_chain(self):
        source = (
            '定义 数列 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]\n'
            '定义 结果 = 数列 |> 筛选(函数(x) => x % 2 == 0) |> 映射(函数(x) => x * x)\n'
            '打印(结果)\n'
        )
        output = capture_output(source)
        assert output.strip() == "[4, 16, 36, 64, 100]"

    def test_pipe_to_function(self):
        source = (
            '函数 双倍(列表)\n'
            '    返回 映射(列表, 函数(x) => x * 2)\n'
            '定义 结果 = [1, 2, 3] |> 双倍\n'
            '打印(结果)\n'
        )
        output = capture_output(source)
        assert output.strip() == "[2, 4, 6]"


# ============================================================
# 成员运算符
# ============================================================

class TestMembershipOperators:
    """成员运算符测试"""

    def test_in_list(self):
        output = capture_output('打印(3 在 [1, 2, 3, 4])\n')
        assert output.strip() == "真"

    def test_not_in_list(self):
        output = capture_output('打印(5 不在 [1, 2, 3, 4])\n')
        assert output.strip() == "真"

    def test_in_string(self):
        output = capture_output('打印("苹" 在 "苹果")\n')
        assert output.strip() == "真"

    def test_in_dict(self):
        output = capture_output('打印("a" 在 {"a": 1, "b": 2})\n')
        assert output.strip() == "真"


# ============================================================
# 模式匹配
# ============================================================

class TestPatternMatching:
    """模式匹配测试"""

    def test_basic_match(self):
        source = (
            '定义 x = 2\n'
            '匹配 x\n'
            '    情况 1: 打印("一")\n'
            '    情况 2: 打印("二")\n'
            '    情况 3: 打印("三")\n'
        )
        output = capture_output(source)
        assert output.strip() == "二"

    def test_match_wildcard(self):
        source = (
            '定义 x = 99\n'
            '匹配 x\n'
            '    情况 1: 打印("一")\n'
            '    情况 _: 打印("其他")\n'
        )
        output = capture_output(source)
        assert output.strip() == "其他"

    def test_match_string(self):
        source = (
            '定义 颜色 = "红"\n'
            '匹配 颜色\n'
            '    情况 "红": 打印("#FF0000")\n'
            '    情况 "绿": 打印("#00FF00")\n'
            '    情况 "蓝": 打印("#0000FF")\n'
            '    情况 _: 打印("未知颜色")\n'
        )
        output = capture_output(source)
        assert output.strip() == "#FF0000"

    def test_match_with_block(self):
        source = (
            '定义 x = 1\n'
            '匹配 x\n'
            '    情况 1:\n'
            '        定义 结果 = "匹配到1"\n'
            '        打印(结果)\n'
            '    情况 2:\n'
            '        打印("匹配到2")\n'
        )
        output = capture_output(source)
        assert output.strip() == "匹配到1"


# ============================================================
# 字符串方法
# ============================================================

class TestStringMethods:
    """字符串方法测试"""

    def test_string_length(self):
        output = capture_output('打印("你好世界".长度)\n')
        assert output.strip() == "4"

    def test_string_split(self):
        output = capture_output('打印("a-b-c".分割("-"))\n')
        assert output.strip() == "['a', 'b', 'c']"

    def test_string_replace(self):
        output = capture_output('打印("你好世界".替换("世界", "道"))\n')
        assert output.strip() == "你好道"

    def test_string_multiply(self):
        output = capture_output('打印("─" * 5)\n')
        assert output.strip() == "─────"


# ============================================================
# 综合测试
# ============================================================

class TestIntegration:
    """综合集成测试"""

    def test_oop_with_functional(self):
        """OOP + 函数式结合"""
        source = (
            '类型 学生\n'
            '    初始化(姓名, 分数)\n'
            '        本对象.姓名 = 姓名\n'
            '        本对象.分数 = 分数\n'
            '定义 学生列表 = [学生("张三", 85), 学生("李四", 92), 学生("王五", 78)]\n'
            '定义 高分 = 筛选(学生列表, 函数(s) => s.分数 >= 80)\n'
            '定义 名字 = 映射(高分, 函数(s) => s.姓名)\n'
            '打印(名字)\n'
        )
        output = capture_output(source)
        assert output.strip() == "['张三', '李四']"

    def test_pipe_with_oop(self):
        """管道 + OOP 结合"""
        source = (
            '类型 商品\n'
            '    初始化(名称, 价格)\n'
            '        本对象.名称 = 名称\n'
            '        本对象.价格 = 价格\n'
            '定义 商品列表 = [商品("书", 30), 商品("笔", 5), 商品("本", 15)]\n'
            '定义 总价 = 商品列表 |> 映射(函数(p) => p.价格) |> 折叠(0, 函数(a, b) => a + b)\n'
            '打印(总价)\n'
        )
        output = capture_output(source)
        assert output.strip() == "50"

    def test_list_concat(self):
        output = capture_output('打印([1, 2] + [3, 4])\n')
        assert output.strip() == "[1, 2, 3, 4]"

    def test_negative_index(self):
        output = capture_output('定义 列表 = [1, 2, 3]\n打印(列表[-1])\n')
        assert output.strip() == "3"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
