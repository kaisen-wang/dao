"""
道语言内建测试运行器
====================

自动发现并运行 .道 测试脚本，汇总标准库「测试」模块生成的测试套件结果，
输出中文报告并按约定返回退出码。无需外部 pytest。

约定文件名：``测试*.道`` 或 ``*_测试.道``。

命令行用法：:

    python -m dao.tools.testrunner 目录
    python -m dao.tools.testrunner 目录 --pattern '测试*.道'

退出码：0 = 全部通过；1 = 有失败用例；2 = 未发现测试文件或无法读取目录。
"""

from __future__ import annotations

import argparse
import time
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path

from ..interpreter import Interpreter
from ..lexer import Lexer
from ..parser import Parser
from ..stdlib.test import DaoTestSuite

默认模式 = ("测试*.道", "*_测试.道")

退出码_全通过 = 0
退出码_有失败 = 1
退出码_无测试 = 2


@dataclass
class 文件结果:
    """单个 .道 测试文件的执行结果。"""

    路径: Path
    成功: bool
    通过: int = 0
    失败: int = 0
    套件数: int = 0
    耗时毫秒: float = 0.0
    错误: str = ""
    失败详情: list[dict] = field(default_factory=list)


@dataclass
class 汇总结果:
    """一次测试运行的汇总结果。"""

    文件结果: list[文件结果]

    @property
    def 通过(self) -> int:
        return sum(结果.通过 for 结果 in self.文件结果)

    @property
    def 失败(self) -> int:
        return sum(结果.失败 for 结果 in self.文件结果)

    @property
    def 退出码(self) -> int:
        if not self.文件结果:
            return 退出码_无测试
        return 退出码_有失败 if self.失败 else 退出码_全通过


def 发现测试文件(
    目录: str | Path, 模式: tuple[str, ...] | list[str] = 默认模式
) -> list[Path]:
    """
    递归发现测试文件。

    文件名匹配 ``测试*.道`` 或 ``*_测试.道``；隐藏目录与 __pycache__ 会被跳过。
    若传入的是单个 .道 文件，则直接返回该文件。
    """
    根 = Path(目录)
    if 根.is_file():
        return [根] if 根.suffix == ".道" else []

    if not 根.is_dir():
        return []

    找到: set[Path] = set()
    for 通配符 in 模式:
        for 路径 in 根.rglob(通配符):
            if not 路径.is_file() or 路径.suffix != ".道":
                continue
            if any(部分.startswith(".") or 部分 == "__pycache__" for 部分 in 路径.parts):
                continue
            找到.add(路径.resolve())
    return sorted(找到, key=lambda 路径: str(路径))


def 执行测试文件(路径: str | Path, 项目目录: str | Path | None = None) -> 文件结果:
    """运行一个 .道 测试文件，提取其中所有 DaoTestSuite 的结果。"""
    文件 = Path(路径)
    结果 = 文件结果(路径=文件, 成功=False)
    起始 = time.perf_counter()
    try:
        源码 = 文件.read_text(encoding="utf-8")
    except OSError as 异常:
        结果.错误 = f"无法读取文件: {异常}"
        return 结果

    根目录 = Path(项目目录) if 项目目录 else 文件.parent
    解释器 = Interpreter(project_dir=str(根目录))
    解释器.module_search_paths.insert(0, str(根目录))

    try:
        词法 = Lexer(源码, str(文件))
        语法树 = Parser(词法.tokenize(), 源码).parse()
        # 脚本自带的 打印(测试报告(...)) 由运行器统一汇总，避免重复输出。
        with redirect_stdout(StringIO()):
            解释器.execute(语法树, source=源码)
    except SystemExit as 异常:
        结果.错误 = f"测试脚本调用了退出({异常.code})"
    except Exception as 异常:
        结果.错误 = f"执行异常: {type(异常).__name__}: {异常}"

    try:
        套件列表 = [
            值
            for 值 in 解释器.global_env.values.values()
            if isinstance(值, DaoTestSuite)
        ]
    except Exception as 异常:  # 极端情况下解释器状态被破坏
        套件列表 = []
        结果.错误 = (结果.错误 + "; " if 结果.错误 else "") + f"读取测试套件失败: {异常}"

    结果.耗时毫秒 = (time.perf_counter() - 起始) * 1000
    结果.套件数 = len(套件列表)
    结果.通过 = sum(套件.passed for 套件 in 套件列表)
    结果.失败 = sum(套件.failed for 套件 in 套件列表)
    for 套件 in 套件列表:
        结果.失败详情.extend(套件.failures)

    if not 套件列表 and not 结果.错误:
        结果.错误 = "未发现测试套件（应使用 测试套件(名称) 创建）"
    结果.成功 = (
        not 结果.错误
        and 结果.失败 == 0
        and 结果.套件数 > 0
    )
    return 结果


def 运行测试(
    目录: str | Path, 模式: tuple[str, ...] | list[str] = 默认模式
) -> 汇总结果:
    """发现并运行目录下所有测试文件。"""
    文件列表 = 发现测试文件(目录, 模式)
    return 汇总结果([执行测试文件(路径) for 路径 in 文件列表])


def 生成报告(结果: 汇总结果, 显示详情: bool = True) -> str:
    """生成中文测试报告。"""
    总文件 = len(结果.文件结果)
    成功文件 = sum(1 for 文件 in 结果.文件结果 if 文件.成功)
    行 = [
        "=== 道语言测试运行器 ===",
        f"测试文件: {总文件}，成功: {成功文件}，失败: {总文件 - 成功文件}",
        f"用例总计: {结果.通过 + 结果.失败}，通过: {结果.通过}，失败: {结果.失败}",
        "",
    ]
    for 文件 in 结果.文件结果:
        标记 = "通过" if 文件.成功 else "失败"
        行.append(
            f"[{标记}] {文件.路径} （套件 {文件.套件数}，"
            f"通过 {文件.通过}，失败 {文件.失败}，{文件.耗时毫秒:.2f} 毫秒）"
        )
        if 文件.错误:
            行.append(f"    错误: {文件.错误}")
        if 显示详情:
            for 详情 in 文件.失败详情:
                行.append(
                    f"    - {详情.get('名称')}: "
                    f"期望 {详情.get('期望')}，实际 {详情.get('实际')}"
                )
    if not 总文件:
        行.append("未发现测试文件（约定文件名：测试*.道 或 *_测试.道）")
    行.append("")
    行.append(f"运行结果: {'全部通过' if 结果.退出码 == 退出码_全通过 else ('存在失败' if 结果.退出码 == 退出码_有失败 else '未发现测试')}")
    return "\n".join(行)


def main(argv: list[str] | None = None) -> int:
    """``python -m dao.tools.testrunner`` 的命令行入口。"""
    解析器 = argparse.ArgumentParser(
        prog="python -m dao.tools.testrunner",
        description="发现并运行 .道 测试脚本，输出中文测试报告",
    )
    解析器.add_argument(
        "目录", nargs="?", default=".", help="待扫描的目录（默认当前目录）"
    )
    解析器.add_argument(
        "-p",
        "--pattern",
        action="append",
        dest="模式",
        help="自定义文件名模式，可重复指定；默认 测试*.道 与 *_测试.道",
    )
    解析器.add_argument(
        "-q", "--quiet", action="store_true", help="仅输出汇总行，不显示逐文件详情"
    )
    参数 = 解析器.parse_args(argv)

    模式 = tuple(参数.模式) if 参数.模式 else 默认模式
    结果 = 运行测试(参数.目录, 模式)
    print(生成报告(结果, 显示详情=not 参数.quiet))
    return 结果.退出码


if __name__ == "__main__":
    raise SystemExit(main())
