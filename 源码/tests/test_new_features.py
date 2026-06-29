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

    def test_分组(self):
        source = (
            '定义 数列 = [1, 2, 3, 4, 5, 6]\n'
            '定义 结果 = 分组(数列, 函数(x) => x % 2)\n'
            '打印(结果[0])\n'
            '打印(结果[1])\n'
        )
        output = capture_output(source)
        assert "[2, 4, 6]" in output
        assert "[1, 3, 5]" in output


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


class TestEnumPatternMatching:
    """枚举模式匹配测试"""

    def test_enum_variant_match(self):
        source = (
            '枚举 结果\n'
            '    成功(值)\n'
            '    失败(错误信息)\n'
            '定义 r = 结果.成功(42)\n'
            '匹配 r\n'
            '    情况 结果.成功(值):\n'
            '        打印(值)\n'
            '    情况 结果.失败(信息):\n'
            '        打印(信息)\n'
        )
        output = capture_output(source)
        assert output.strip() == "42"

    def test_enum_variant_match_failure(self):
        source = (
            '枚举 结果\n'
            '    成功(值)\n'
            '    失败(错误信息)\n'
            '定义 r = 结果.失败("未找到")\n'
            '匹配 r\n'
            '    情况 结果.成功(值):\n'
            '        打印(值)\n'
            '    情况 结果.失败(信息):\n'
            '        打印(信息)\n'
        )
        output = capture_output(source)
        assert output.strip() == "未找到"

    def test_enum_simple_variant_match(self):
        source = (
            '枚举 颜色\n'
            '    红\n'
            '    绿\n'
            '    蓝\n'
            '定义 c = 颜色.红\n'
            '匹配 c\n'
            '    情况 颜色.红: 打印("红色")\n'
            '    情况 颜色.绿: 打印("绿色")\n'
            '    情况 _: 打印("其他")\n'
        )
        output = capture_output(source)
        assert output.strip() == "红色"


class TestTypeCheckPattern:
    """类型检查模式测试"""

    def test_type_check_list(self):
        source = (
            '定义 x = [1, 2, 3]\n'
            '匹配 x\n'
            '    情况 n 当 取类型(n) == "列表": 打印("是列表")\n'
            '    情况 _: 打印("其他")\n'
        )
        output = capture_output(source)
        assert output.strip() == "是列表"

    def test_type_check_number(self):
        source = (
            '定义 x = 42\n'
            '匹配 x\n'
            '    情况 n 当 取类型(n) == "数值": 打印("是数值")\n'
            '    情况 _: 打印("其他")\n'
        )
        output = capture_output(source)
        assert output.strip() == "是数值"


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


class TestStaticMethods:
    """测试静态方法"""

    def test_static_method_call(self):
        """调用静态方法"""
        output = capture_output(
            '类型 数学\n'
            '    静态 函数 加法(a, b)\n'
            '        返回 a + b\n'
            '打印(数学.加法(3, 4))\n'
        )
        assert output.strip() == "7"

    def test_multiple_static_methods(self):
        """多个静态方法"""
        output = capture_output(
            '类型 工具\n'
            '    静态 函数 平方(x)\n'
            '        返回 x * x\n'
            '    静态 函数 立方(x)\n'
            '        返回 x * x * x\n'
            '打印(工具.平方(3))\n'
            '打印(工具.立方(3))\n'
        )
        assert output.strip() == "9\n27"

    def test_static_with_instance_methods(self):
        """静态方法与实例方法共存"""
        output = capture_output(
            '类型 计数器\n'
            '    初始化()\n'
            '        本对象.值 = 0\n'
            '    函数 增加()\n'
            '        本对象.值 = 本对象.值 + 1\n'
            '    静态 函数 创建(初始值)\n'
            '        定义 c = 计数器()\n'
            '        c.值 = 初始值\n'
            '        返回 c\n'
            '定义 c = 计数器.创建(10)\n'
            '打印(c.值)\n'
        )
        assert output.strip() == "10"


class TestAccessControl:
    """测试访问控制"""

    def test_private_method_internal_access(self):
        """类内部可以访问私有方法"""
        output = capture_output(
            '类型 账户\n'
            '    初始化(余额)\n'
            '        本对象.余额 = 余额\n'
            '    私有 函数 验证(金额)\n'
            '        返回 金额 > 0\n'
            '    函数 存款(金额)\n'
            '        如果 本对象.验证(金额)\n'
            '            本对象.余额 = 本对象.余额 + 金额\n'
            '        返回 本对象.余额\n'
            '定义 a = 账户(100)\n'
            '打印(a.存款(50))\n'
        )
        assert output.strip() == "150"

    def test_private_method_external_access_denied(self):
        """类外部无法访问私有方法"""
        with pytest.raises(运行时错误):
            run(
                '类型 账户\n'
                '    初始化()\n'
                '        本对象.值 = 0\n'
                '    私有 函数 内部()\n'
                '        返回 本对象.值\n'
                '定义 a = 账户()\n'
                'a.内部()\n'
            )


class TestTemplateStrings:
    """测试模板字符串"""

    def test_simple_template(self):
        """简单模板字符串"""
        output = capture_output('定义 名字 = "世界"\n打印(`你好 {名字}`)\n')
        assert output.strip() == "你好 世界"

    def test_template_with_expression(self):
        """模板字符串中的表达式"""
        output = capture_output('定义 x = 10\n打印(`结果是 {x + 5}`)\n')
        assert output.strip() == "结果是 15"

    def test_template_multiple_expressions(self):
        """多个表达式的模板字符串"""
        output = capture_output(
            '定义 名字 = "张三"\n'
            '定义 年龄 = 25\n'
            '打印(`{名字}今年{年龄}岁`)\n'
        )
        assert output.strip() == "张三今年25岁"

    def test_template_no_expression(self):
        """没有表达式的模板字符串"""
        output = capture_output('打印(`纯文本`)\n')
        assert output.strip() == "纯文本"

    def test_template_with_boolean(self):
        """模板字符串中的布尔值"""
        output = capture_output('打印(`值是{真}`)\n')
        assert output.strip() == "值是真"

    def test_template_with_null(self):
        """模板字符串中的空值"""
        output = capture_output('打印(`值是{空}`)\n')
        assert output.strip() == "值是空"

    def test_template_with_function_call(self):
        """模板字符串中调用函数"""
        output = capture_output(
            '函数 加法(a, b)\n'
            '    返回 a + b\n'
            '打印(`结果：{加法(3, 4)}`)\n'
        )
        assert output.strip() == "结果：7"

    def test_template_with_member_access(self):
        """模板字符串中访问成员"""
        output = capture_output(
            '类型 人\n'
            '    初始化(名字)\n'
            '        本对象.名字 = 名字\n'
            '定义 张三 = 人("张三")\n'
            '打印(`他叫{张三.名字}`)\n'
        )
        assert output.strip() == "他叫张三"

    def test_template_as_variable(self):
        """模板字符串赋值给变量"""
        output = capture_output(
            '定义 x = 42\n'
            '定义 消息 = `答案是{x}`\n'
            '打印(消息)\n'
        )
        assert output.strip() == "答案是42"


class TestDestructuringAssignment:
    """测试解构赋值"""

    def test_list_destructure_decl(self):
        """定义列表解构赋值"""
        output = capture_output(
            '定义 [甲, 乙, 丙] = [10, 20, 30]\n'
            '打印(甲)\n'
            '打印(乙)\n'
            '打印(丙)\n'
        )
        assert output.strip() == "10\n20\n30"

    def test_list_destructure_assign(self):
        """列表解构赋值（非声明）"""
        output = capture_output(
            '定义 甲 = 0\n'
            '定义 乙 = 0\n'
            '[甲, 乙] = [100, 200]\n'
            '打印(甲)\n'
            '打印(乙)\n'
        )
        assert output.strip() == "100\n200"

    def test_destructure_with_expressions(self):
        """解构赋值表达式"""
        output = capture_output(
            '函数 获取数据()\n'
            '    返回 [1, 2, 3]\n'
            '定义 [x, y, z] = 获取数据()\n'
            '打印(x + y + z)\n'
        )
        assert output.strip() == "6"

    def test_destructure_swap(self):
        """解构赋值交换变量"""
        output = capture_output(
            '定义 a = 1\n'
            '定义 b = 2\n'
            '[a, b] = [b, a]\n'
            '打印(a)\n'
            '打印(b)\n'
        )
        assert output.strip() == "2\n1"

    def test_destructure_mismatch_raises(self):
        """解构赋值数量不匹配报错"""
        with pytest.raises(运行时错误):
            run('定义 [甲, 乙] = [1, 2, 3]\n')

    def test_dict_destructure(self):
        """字典解构赋值"""
        output = capture_output(
            '定义 数据 = {"甲": 10, "乙": 20}\n'
            '定义 [甲, 乙] = [数据["甲"], 数据["乙"]]\n'
            '打印(甲)\n'
            '打印(乙)\n'
        )
        assert output.strip() == "10\n20"


class TestCurrying:
    """柯里化测试"""

    def test_simple_currying(self):
        source = (
            '函数 加法(甲, 乙)\n'
            '    返回 甲 + 乙\n'
            '定义 加法柯里化 = 柯里化(加法)\n'
            '定义 加5 = 加法柯里化(5)\n'
            '打印(加5(3))\n'
        )
        output = capture_output(source)
        assert output.strip() == "8"

    def test_currying_three_params(self):
        source = (
            '函数 累加(甲, 乙, 丙)\n'
            '    返回 甲 + 乙 + 丙\n'
            '定义 累加柯里化 = 柯里化(累加)\n'
            '定义 加1 = 累加柯里化(1)\n'
            '定义 加1再加2 = 加1(2)\n'
            '打印(加1再加2(3))\n'
        )
        output = capture_output(source)
        assert output.strip() == "6"

    def test_currying_partial_application(self):
        source = (
            '函数 乘法(甲, 乙)\n'
            '    返回 甲 * 乙\n'
            '定义 乘法柯里化 = 柯里化(乘法)\n'
            '定义 双倍 = 乘法柯里化(2)\n'
            '打印(双倍(5))\n'
            '打印(双倍(10))\n'
        )
        output = capture_output(source)
        assert output.strip() == "10\n20"

    def test_currying_with_pipe(self):
        source = (
            '函数 加法(甲, 乙)\n'
            '    返回 甲 + 乙\n'
            '定义 加法柯里化 = 柯里化(加法)\n'
            '定义 数据 = [1, 2, 3, 4, 5]\n'
            '定义 结果 = 映射(数据, 加法柯里化(10))\n'
            '打印(结果[2])\n'
        )
        output = capture_output(source)
        assert output.strip() == "13"

    def test_currying_with_lambda(self):
        source = (
            '定义 乘法 = 函数(甲, 乙) => 甲 * 乙\n'
            '定义 乘法柯里化 = 柯里化(乘法)\n'
            '定义 三倍 = 乘法柯里化(3)\n'
            '打印(三倍(7))\n'
        )
        output = capture_output(source)
        assert output.strip() == "21"


class TestFunctionComposition:
    """函数组合测试"""

    def test_simple_compose(self):
        source = (
            '函数 加10(数值)\n'
            '    返回 数值 + 10\n'
            '函数 乘2(数值)\n'
            '    返回 数值 * 2\n'
            '定义 组合函数 = 组合(加10, 乘2)\n'
            '打印(组合函数(5))\n'
        )
        output = capture_output(source)
        assert output.strip() == "20"

    def test_compose_three_functions(self):
        source = (
            '函数 加1(数值)\n'
            '    返回 数值 + 1\n'
            '函数 平方(数值)\n'
            '    返回 数值 * 数值\n'
            '函数 减5(数值)\n'
            '    返回 数值 - 5\n'
            '定义 组合函数 = 组合(加1, 减5, 平方)\n'
            '打印(组合函数(4))\n'
        )
        output = capture_output(source)
        assert output.strip() == "12"

    def test_pipe_compose(self):
        source = (
            '函数 加10(数值)\n'
            '    返回 数值 + 10\n'
            '函数 乘2(数值)\n'
            '    返回 数值 * 2\n'
            '定义 管道组合函数 = 管道组合(加10, 乘2)\n'
            '打印(管道组合函数(5))\n'
        )
        output = capture_output(source)
        assert output.strip() == "30"

    def test_compose_with_map(self):
        source = (
            '函数 加10(数值)\n'
            '    返回 数值 + 10\n'
            '函数 乘2(数值)\n'
            '    返回 数值 * 2\n'
            '定义 组合函数 = 组合(加10, 乘2)\n'
            '定义 数据 = [1, 2, 3, 4, 5]\n'
            '定义 结果 = 映射(数据, 组合函数)\n'
            '打印(结果[2])\n'
        )
        output = capture_output(source)
        assert output.strip() == "16"

    def test_compose_single_function(self):
        source = (
            '函数 加10(数值)\n'
            '    返回 数值 + 10\n'
            '定义 组合函数 = 组合(加10)\n'
            '打印(组合函数(5))\n'
        )
        output = capture_output(source)
        assert output.strip() == "15"


class TestGenerators:
    """生成器测试"""

    def test_simple_generator(self):
        source = (
            '函数 生成器(上限)\n'
            '    定义 计数器 = 0\n'
            '    当 计数器 < 上限\n'
            '        产出 计数器\n'
            '        计数器 = 计数器 + 1\n'
            '定义 生成器实例 = 生成器(5)\n'
            '打印(下一个(生成器实例))\n'
            '打印(下一个(生成器实例))\n'
            '打印(下一个(生成器实例))\n'
        )
        output = capture_output(source)
        assert output.strip() == "0\n1\n2"

    def test_generator_with_foreach(self):
        source = (
            '函数 生成器(上限)\n'
            '    定义 计数器 = 0\n'
            '    当 计数器 < 上限\n'
            '        产出 计数器\n'
            '        计数器 = 计数器 + 1\n'
            '定义 生成器实例 = 生成器(5)\n'
            '遍历 数值 在 生成器实例\n'
            '    打印(数值)\n'
        )
        output = capture_output(source)
        assert output.strip() == "0\n1\n2\n3\n4"

    def test_generator_infinite(self):
        source = (
            'function 无限生成器()\n'
            '    定义 计数器 = 0\n'
            '    当 真\n'
            '        产出 计数器\n'
            '        计数器 = 计数器 + 1\n'
        )


class TestLazyStream:
    """惰性流测试"""

    def test_stream_from_list(self):
        source = (
            '定义 数字列表 = [1, 2, 3, 4, 5]\n'
            '定义 结果 = 取(映射流(数字列表, 函数(x) => x * x), 3)\n'
            '打印(结果)\n'
        )
        output = capture_output(source)
        assert output.strip() == "[1, 4, 9]"

    def test_stream_filter(self):
        source = (
            '定义 数字列表 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]\n'
            '定义 结果 = 取(筛选流(数字列表, 函数(x) => x % 2 == 0), 3)\n'
            '打印(结果)\n'
        )
        output = capture_output(source)
        assert output.strip() == "[2, 4, 6]"

    def test_stream_chain(self):
        source = (
            '定义 数字列表 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]\n'
            '定义 偶数平方流 = 筛选流(映射流(数字列表, 函数(x) => x * x), 函数(x) => x % 2 == 0)\n'
            '定义 结果 = 取(偶数平方流, 3)\n'
            '打印(结果)\n'
        )
        output = capture_output(source)
        assert output.strip() == "[4, 16, 36]"

    def test_stream_from_generator(self):
        source = (
            '函数 自然数()\n'
            '    定义 n = 0\n'
            '    当 真\n'
            '        产出 n\n'
            '        n = n + 1\n'
            '定义 偶数平方流 = 筛选流(映射流(自然数(), 函数(x) => x * x), 函数(x) => x % 2 == 0)\n'
            '定义 结果 = 取(偶数平方流, 5)\n'
            '打印(结果)\n'
        )
        output = capture_output(source)
        assert output.strip() == "[0, 4, 16, 36, 64]"

    def test_stream_take_from_list(self):
        source = (
            '定义 列表 = [10, 20, 30, 40, 50]\n'
            '定义 结果 = 取(列表, 3)\n'
            '打印(结果)\n'
        )
        output = capture_output(source)
        assert output.strip() == "[10, 20, 30]"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
