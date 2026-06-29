import sys
import os
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.stdlib.math import (
    _stdlib_正弦, _stdlib_余弦, _stdlib_正切,
    _stdlib_反正弦, _stdlib_反余弦, _stdlib_反正切,
    _stdlib_随机整数, _stdlib_随机小数, _stdlib_随机选择, _stdlib_打乱,
    _stdlib_平均值, _stdlib_中位数, _stdlib_标准差,
    _stdlib_向上取整, _stdlib_向下取整, _stdlib_四舍五入,
    _stdlib_幂, _stdlib_自然对数, _stdlib_对数,
    create_module_env,
)
from dao.errors import 运行时错误


class TestMathTrig:
    def test_sin(self):
        assert abs(_stdlib_正弦(0) - 0.0) < 1e-10

    def test_cos(self):
        assert abs(_stdlib_余弦(0) - 1.0) < 1e-10

    def test_tan(self):
        assert abs(_stdlib_正切(0) - 0.0) < 1e-10

    def test_asin(self):
        assert abs(_stdlib_反正弦(1) - math.pi / 2) < 1e-10

    def test_asin_out_of_range(self):
        try:
            _stdlib_反正弦(2)
            assert False, "应抛出运行时错误"
        except 运行时错误:
            pass

    def test_acos(self):
        assert abs(_stdlib_反余弦(0) - math.pi / 2) < 1e-10


class TestMathRandom:
    def test_randint(self):
        for _ in range(100):
            val = _stdlib_随机整数(1, 10)
            assert 1 <= val <= 10

    def test_randint_invalid_range(self):
        try:
            _stdlib_随机整数(10, 1)
            assert False, "应抛出运行时错误"
        except 运行时错误:
            pass

    def test_random(self):
        val = _stdlib_随机小数()
        assert 0.0 <= val < 1.0

    def test_choice(self):
        lst = ["甲", "乙", "丙"]
        val = _stdlib_随机选择(lst)
        assert val in lst

    def test_shuffle(self):
        lst = [1, 2, 3, 4, 5]
        result = _stdlib_打乱(lst)
        assert sorted(result) == lst
        assert lst == [1, 2, 3, 4, 5]


class TestMathStats:
    def test_mean(self):
        assert abs(_stdlib_平均值([1, 2, 3, 4, 5]) - 3.0) < 1e-10

    def test_mean_empty(self):
        try:
            _stdlib_平均值([])
            assert False, "应抛出运行时错误"
        except 运行时错误:
            pass

    def test_median(self):
        assert _stdlib_中位数([1, 2, 3, 4, 5]) == 3

    def test_stdev(self):
        assert abs(_stdlib_标准差([2, 4, 4, 4, 5, 5, 7, 9]) - 2.0) < 0.2


class TestMathRounding:
    def test_ceil(self):
        assert _stdlib_向上取整(3.2) == 4

    def test_floor(self):
        assert _stdlib_向下取整(3.8) == 3

    def test_round(self):
        assert _stdlib_四舍五入(3.5) == 4


class TestMathPowerLog:
    def test_pow(self):
        assert _stdlib_幂(2, 10) == 1024.0

    def test_log(self):
        assert abs(_stdlib_对数(100, 10) - 2.0) < 1e-10

    def test_ln(self):
        assert abs(_stdlib_自然对数(math.e) - 1.0) < 1e-10


class TestMathModuleEnv:
    def test_create_module_env(self):
        env = create_module_env()
        assert "正弦" in env.values
        assert "圆周率" in env.values
        assert abs(env.values["圆周率"] - math.pi) < 1e-10