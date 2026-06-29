"""
字典解构测试
============
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


class TestDictDestructure:
    def test_basic_dict_destructure(self):
        env = eval_env(
            '定义 人 = {"姓名": "张三", "年龄": 30}\n'
            '定义 {姓名, 年龄} = 人\n'
        )
        assert env.get("姓名") == "张三"
        assert env.get("年龄") == 30

    def test_dict_destructure_with_rename(self):
        env = eval_env(
            '定义 人 = {"姓名": "李四", "年龄": 25}\n'
            '定义 {姓名: 名, 年龄: 岁} = 人\n'
        )
        assert env.get("名") == "李四"
        assert env.get("岁") == 25

    def test_dict_destructure_partial(self):
        env = eval_env(
            '定义 人 = {"姓名": "王五", "年龄": 30, "城市": "北京"}\n'
            '定义 {姓名} = 人\n'
        )
        assert env.get("姓名") == "王五"

    def test_list_destructure_still_works(self):
        env = eval_env("定义 [甲, 乙] = [10, 20]\n")
        assert env.get("甲") == 10
        assert env.get("乙") == 20