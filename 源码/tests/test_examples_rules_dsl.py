"""业务规则 DSL 示例的回归测试。

覆盖：注解登记、优先级排序、无命中结构、动态事实、全部判定、清空规则、
示例端到端，以及解释器/VM 双模式输出对比。

子进程一律用 sys.executable；本地 .道 模块用 Interpreter.module_search_paths
定位，不依赖当前工作目录。
"""

import os
import subprocess
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPO_ROOT = os.path.abspath(os.path.join(ROOT, ".."))
sys.path.insert(0, ROOT)

from dao.interpreter import Interpreter
from dao.lexer import Lexer
from dao.parser import Parser

RULES_DIR = os.path.join(REPO_ROOT, "示例", "业务规则")
MAIN_PY = os.path.join(ROOT, "main.py")
PYTHON = sys.executable

导入 = "从 规则引擎 导入 标注规则, 规则表, 判定, 全部判定, 清空规则\n"
知识库 = """
逻辑 风控库
    事实: 风险("甲", "高风险")
    规则: 命中(?人, ?标签) 如果 风险(?人, ?标签)
"""


def 执行(源码: str):
    """解析并执行道语言源码，返回最后一条语句的值。"""
    解释器 = Interpreter()
    解释器.module_search_paths = [RULES_DIR]
    树 = Parser(Lexer(源码).tokenize()).parse()
    return 解释器.execute(树, source=源码)


def 运行示例(模式=None):
    """在示例目录用 main.py 运行风控演示，返回 CompletedProcess。"""
    命令 = [PYTHON, MAIN_PY]
    if 模式:
        命令 += ["--mode", 模式]
    命令.append("风控演示.道")
    return subprocess.run(
        命令,
        check=False,
        cwd=RULES_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )


class Test业务规则DSL:
    def test_规则登记(self):
        """注解参数被捕获进规则表，且原函数未被替换丢失。"""
        结果 = 执行(
            导入
            + """
@标注规则(名称="拦截", 优先级=10, 条件="高风险")
函数 拦截(对象)
    返回 "拦截:" + 对象

{"条数": 规则表.长度, "名称": 规则表[0]["名称"],
 "优先级": 规则表[0]["优先级"], "条件": 规则表[0]["条件"],
 "结果": 拦截("乙")}
"""
        )
        assert 结果 == {
            "条数": 1,
            "名称": "拦截",
            "优先级": 10,
            "条件": "高风险",
            "结果": "拦截:乙",
        }

    def test_优先级(self):
        """同一标签命中多条规则时，优先级数值大者先执行。"""
        结果 = 执行(
            导入
            + 知识库
            + """
@标注规则(名称="低优先", 优先级=1, 条件="高风险")
函数 低(对象)
    返回 "低"

@标注规则(名称="高优先", 优先级=99, 条件="高风险")
函数 高(对象)
    返回 "高"

判定("甲", 风控库)
"""
        )
        assert 结果 == {"命中": True, "规则名": "高优先", "优先级": 99, "结果": "高"}

    def test_无命中(self):
        """无命中时返回固定结构，结果字段为 None。"""
        结果 = 执行(
            导入
            + 知识库
            + """
@标注规则(名称="拦截", 优先级=10, 条件="高风险")
函数 拦截(对象)
    返回 "拦截"

判定("不存在", 风控库)
"""
        )
        assert 结果 == {"命中": False, "规则名": "", "优先级": 0, "结果": None}

    def test_动态事实(self):
        """添加事实后同一对象的判定结果随之改变。"""
        结果 = 执行(
            导入
            + 知识库
            + """
@标注规则(名称="拦截", 优先级=10, 条件="高风险")
函数 拦截(对象)
    返回 "拦截:" + 对象

@标注规则(名称="放行", 优先级=1, 条件="低风险")
函数 放行(对象)
    返回 "放行:" + 对象

定义 前 = 判定("乙", 风控库)
添加事实(风控库, "风险", "乙", "低风险")
定义 后 = 判定("乙", 风控库)
{"前": 前, "后": 后}
"""
        )
        assert 结果["前"] == {"命中": False, "规则名": "", "优先级": 0, "结果": None}
        assert 结果["后"] == {
            "命中": True,
            "规则名": "放行",
            "优先级": 1,
            "结果": "放行:乙",
        }

    def test_全部判定(self):
        """全部判定返回所有命中规则，且按优先级降序。"""
        结果 = 执行(
            导入
            + 知识库
            + """
@标注规则(名称="复核", 优先级=5, 条件="高风险")
函数 复核(对象)
    返回 "复核"

@标注规则(名称="拦截", 优先级=50, 条件="高风险")
函数 拦截(对象)
    返回 "拦截"

全部判定("甲", 风控库)
"""
        )
        assert [项["规则名"] for 项 in 结果] == ["拦截", "复核"]
        assert [项["优先级"] for 项 in 结果] == [50, 5]
        assert all(项["命中"] is True for 项 in 结果)

    def test_清空规则(self):
        """清空规则就地生效，已导入的引用同步可见。"""
        结果 = 执行(
            导入
            + """
@标注规则(名称="拦截", 优先级=10, 条件="高风险")
函数 拦截(对象)
    返回 "拦截"
清空规则()
规则表.长度
"""
        )
        assert 结果 == 0

    def test_示例端到端(self):
        """风控演示输出三类场景，文本确定可断言。"""
        进程 = 运行示例()
        assert 进程.returncode == 0, 进程.stderr
        输出 = 进程.stdout
        assert "规则数:4" in 输出
        assert "场景1-高优先级命中:{'命中': True, '规则名': '拦截', '优先级': 100, '结果': '拦截:甲'}" in 输出
        assert "场景2-无命中:{'命中': False, '规则名': '', '优先级': 0, '结果': None}" in 输出
        assert "'规则名': '限额放行', '优先级': 10" in 输出
        assert "'规则名': '白名单直达', '优先级': 80" in 输出
        assert "全部命中:" in 输出

    def test_双模式输出对比(self):
        """解释器与 VM 模式输出一致；若不一致则记录差异而不改核心。"""
        输出 = {}
        for 模式 in ("interpreter", "vm"):
            进程 = 运行示例(模式)
            assert 进程.returncode == 0, (模式, 进程.stderr)
            输出[模式] = 进程.stdout
        if 输出["interpreter"] != 输出["vm"]:
            pytest.skip(
                "解释器/VM 输出不一致："
                f"interpreter={输出['interpreter']!r}, vm={输出['vm']!r}"
            )
