"""
抽象类型测试
================

测试 抽象 类型 关键字的功能：
- 声明抽象类
- 抽象方法
- 抽象类不能被实例化
- 具体类必须实现所有抽象方法
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.lexer import Lexer
from dao.parser import Parser
from dao.interpreter import Interpreter
from dao.errors import 运行时错误, 类型错误
from dao.ast_nodes import AbstractDecl, ClassDecl, FunctionDecl


def parse(source: str):
    """辅助函数：解析源代码"""
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse()


def execute(source: str):
    """辅助函数：执行源代码"""
    ast = parse(source)
    interpreter = Interpreter()
    interpreter.execute(ast)
    return interpreter.global_env.values


def test_abstract_class_declaration():
    """测试抽象类声明"""
    source = """
抽象 类型 形状
    抽象 获取面积()
"""
    ast = parse(source)
    assert len(ast.statements) == 1
    assert isinstance(ast.statements[0], AbstractDecl)
    assert ast.statements[0].name == "形状"


def test_abstract_method_in_class():
    """测试类中的抽象方法"""
    source = """
类型 形状
    抽象 获取面积()
"""
    ast = parse(source)
    assert len(ast.statements) == 1
    assert isinstance(ast.statements[0], ClassDecl)
    assert len(ast.statements[0].body) == 1
    assert isinstance(ast.statements[0].body[0], FunctionDecl)
    assert ast.statements[0].body[0].is_abstract == True


def test_abstract_class_cannot_be_instantiated():
    """测试抽象类不能被实例化"""
    source = """
抽象 类型 形状
    抽象 获取面积()

定义 s = 形状()
"""
    try:
        execute(source)
        assert False, "应该抛出运行时错误"
    except 运行时错误 as e:
        assert "抽象类" in str(e).lower() or "不能被实例化" in str(e)


def test_concrete_class_must_implement_abstract_methods():
    """测试具体类必须实现所有抽象方法"""
    source = """
抽象 类型 形状
    抽象 获取面积()

类型 圆形 继承自 形状
    初始化(半径)
        本对象.半径 = 半径
"""
    try:
        execute(source)
        assert False, "应该抛出类型错误"
    except 类型错误 as e:
        assert "必须实现" in str(e) and "抽象方法" in str(e)


def test_concrete_class_implements_abstract_methods():
    """测试具体类正确实现抽象方法"""
    source = """
抽象 类型 形状
    抽象 获取面积()

类型 圆形 继承自 形状
    初始化(半径)
        本对象.半径 = 半径

    函数 获取面积()
        返回 3.14159 * 本对象.半径 * 本对象.半径

定义 c = 圆形(5)
定义 area = c.获取面积()
"""
    result = execute(source)
    # 面积应该接近 78.53975
    assert "area" in result
    assert abs(result["area"] - 78.53975) < 0.0001


def test_abstract_class_with_multiple_abstract_methods():
    """测试包含多个抽象方法的抽象类"""
    source = """
抽象 类型 动物
    抽象 发出声音()
    抽象 移动()

类型 狗 继承自 动物
    初始化(名字)
        本对象.名字 = 名字

    函数 发出声音()
        返回 "汪汪"

    函数 移动()
        返回 "跑"

定义 d = 狗("旺财")
定义 sound = d.发出声音()
定义 move = d.移动()
"""
    result = execute(source)
    assert result["sound"] == "汪汪"
    assert result["move"] == "跑"


def test_abstract_class_inheritance_chain():
    """测试抽象类继承链"""
    source = """
抽象 类型 车辆
    抽象 启动()
    抽象 停止()

抽象 类型 电动汽车 继承自 车辆
    抽象 充电()

类型 特斯拉 继承自 电动汽车
    初始化(型号)
        本对象.型号 = 型号

    函数 启动()
        返回 "启动 特斯拉 " + 本对象.型号

    函数 停止()
        返回 "停止 特斯拉 " + 本对象.型号

    函数 充电()
        返回 "正在充电..."

定义 car = 特斯拉("Model 3")
定义 start = car.启动()
定义 stop = car.停止()
定义 charge = car.充电()
"""
    result = execute(source)
    assert "启动 特斯拉 Model 3" in result["start"]
    assert "停止 特斯拉 Model 3" in result["stop"]
    assert result["charge"] == "正在充电..."


def test_abstract_class_with_concrete_methods():
    """测试抽象类可以有具体方法"""
    source = """
抽象 类型 列表
    抽象 获取长度()

    函数 为空()
        返回 本对象.获取长度() == 0

类型 数组 继承自 列表
    初始化(元素)
        本对象.元素 = 元素

    函数 获取长度()
        返回 长度(本对象.元素)

定义 arr = 数组([1, 2, 3])
定义 length = arr.获取长度()
定义 is_empty = arr.为空()
"""
    result = execute(source)
    assert result["length"] == 3
    assert result["is_empty"] == False


def test_abstract_class_with_static_methods():
    """测试抽象类可以有静态方法"""
    source = """
抽象 类型 工具
    抽象 处理(数据)

    静态 函数 创建()
        返回 "抽象工具实例"

定义 info = 工具.创建()
"""
    result = execute(source)
    assert result["info"] == "抽象工具实例"


def test_concrete_class_can_override_concrete_methods():
    """测试具体类可以重写父类的具体方法"""
    source = """
抽象 类型 父类
    抽象 抽象方法()

    函数 具体方法()
        返回 "父类的实现"

类型 子类 继承自 父类
    函数 抽象方法()
        返回 "子类实现了抽象方法"

    函数 具体方法()
        返回 "子类的实现"

定义 obj = 子类()
定义 abstract_result = obj.抽象方法()
定义 concrete_result = obj.具体方法()
"""
    result = execute(source)
    assert result["abstract_result"] == "子类实现了抽象方法"
    assert result["concrete_result"] == "子类的实现"


def test_abstract_class_without_abstract_methods():
    """测试没有抽象方法的抽象类（标记为抽象但不能实例化）"""
    source = """
抽象 类型 单例模式
    函数 初始化()
        跳过

定义 instance = 单例模式()
"""
    try:
        execute(source)
        assert False, "应该抛出运行时错误"
    except 运行时错误 as e:
        assert "抽象类" in str(e).lower() or "不能被实例化" in str(e)


if __name__ == "__main__":
    test_abstract_class_declaration()
    test_abstract_method_in_class()
    test_abstract_class_cannot_be_instantiated()
    test_concrete_class_must_implement_abstract_methods()
    test_concrete_class_implements_abstract_methods()
    test_abstract_class_with_multiple_abstract_methods()
    test_abstract_class_inheritance_chain()
    test_abstract_class_with_concrete_methods()
    test_abstract_class_with_static_methods()
    test_concrete_class_can_override_concrete_methods()
    test_abstract_class_without_abstract_methods()
    print("所有测试通过！")
