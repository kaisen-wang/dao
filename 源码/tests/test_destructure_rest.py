"""
解构赋值剩余元素测试
==================
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


class TestDestructureRest:
    def test_rest_element_list(self):
        env = eval_env("定义 [头, ...尾] = [1, 2, 3, 4, 5]\n")
        assert env.get("头") == 1
        assert env.get("尾") == [2, 3, 4, 5]

    def test_rest_element_tuple(self):
        env = eval_env("定义 [头, ...尾] = (10, 20, 30)\n")
        assert env.get("头") == 10
        assert env.get("尾") == (20, 30)

    def test_rest_element_empty(self):
        env = eval_env("定义 [头, ...尾] = [1]\n")
        assert env.get("头") == 1
        assert env.get("尾") == []

    def test_rest_element_multiple_before(self):
        env = eval_env("定义 [甲, 乙, ...尾] = [1, 2, 3, 4]\n")
        assert env.get("甲") == 1
        assert env.get("乙") == 2
        assert env.get("尾") == [3, 4]

    def test_destructure_without_rest_still_works(self):
        env = eval_env("定义 [甲, 乙] = [10, 20]\n")
        assert env.get("甲") == 10
        assert env.get("乙") == 20