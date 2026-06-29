"""
嵌套解构赋值测试
================
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from dao.lexer import Lexer
from dao.parser import Parser
from dao.interpreter import Interpreter


def eval_env(source: str):
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    interpreter = Interpreter()
    interpreter.execute(ast)
    return interpreter.global_env


class TestNestedListDestructure:
    def test_nested_list_destructure(self):
        env = eval_env("定义 [甲, [乙, 丙]] = [1, [2, 3]]\n")
        assert env.get("甲") == 1
        assert env.get("乙") == 2
        assert env.get("丙") == 3

    def test_deeply_nested_list_destructure(self):
        env = eval_env("定义 [甲, [乙, [丙]]] = [1, [2, [3]]]\n")
        assert env.get("甲") == 1
        assert env.get("乙") == 2
        assert env.get("丙") == 3

    def test_nested_list_with_rest(self):
        env = eval_env("定义 [甲, [乙, ...尾]] = [1, [2, 3, 4]]\n")
        assert env.get("甲") == 1
        assert env.get("乙") == 2
        assert env.get("尾") == [3, 4]

    def test_simple_list_destructure_still_works(self):
        env = eval_env("定义 [甲, 乙] = [10, 20]\n")
        assert env.get("甲") == 10
        assert env.get("乙") == 20


class TestNestedDictDestructure:
    def test_nested_dict_destructure(self):
        env = eval_env(
            '定义 数据 = {"用户": {"名字": "王五", "地址": {"城市": "上海"}}}\n'
            '定义 {用户: {名字}} = 数据\n'
        )
        assert env.get("名字") == "王五"

    def test_deeply_nested_dict_destructure(self):
        env = eval_env(
            '定义 数据 = {"用户": {"名字": "王五", "地址": {"城市": "上海"}}}\n'
            '定义 {用户: {名字, 地址: {城市}}} = 数据\n'
        )
        assert env.get("名字") == "王五"
        assert env.get("城市") == "上海"

    def test_dict_destructure_with_rename_nested(self):
        env = eval_env(
            '定义 数据 = {"用户": {"名字": "赵六"}}\n'
            '定义 {用户: {名字: 姓名}} = 数据\n'
        )
        assert env.get("姓名") == "赵六"

    def test_simple_dict_destructure_still_works(self):
        env = eval_env(
            '定义 人 = {"姓名": "张三", "年龄": 30}\n'
            '定义 {姓名, 年龄} = 人\n'
        )
        assert env.get("姓名") == "张三"
        assert env.get("年龄") == 30


class TestMixedNestedDestructure:
    def test_dict_in_list_destructure(self):
        env = eval_env(
            '定义 数据 = [{"名字": "张三"}, 42]\n'
            '定义 [{名字}, 数值] = 数据\n'
        )
        assert env.get("名字") == "张三"
        assert env.get("数值") == 42

    def test_list_in_dict_destructure(self):
        env = eval_env(
            '定义 数据 = {"坐标": [10, 20]}\n'
            '定义 {坐标: [x, y]} = 数据\n'
        )
        assert env.get("x") == 10
        assert env.get("y") == 20