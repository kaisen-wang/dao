"""
内建测试运行器测试
==================

覆盖：测试文件发现、单文件执行、通过/失败汇总、异常文件、无套件文件、
中文报告、退出码语义、CLI 入口。
"""

from __future__ import annotations

from dao.tools.testrunner import (
    main,
    发现测试文件,
    执行测试文件,
    生成报告,
    运行测试,
    默认模式,
)

通过脚本 = """\
从 测试 导入 测试套件, 断言等于, 测试报告
定义 套件 = 测试套件("加法")
套件.start()
尝试
    断言等于(1 + 1, 2)
    套件.record_pass("一加一")
捕获 错误
    套件.record_fail("一加一", "2", 文本(错误))
打印(测试报告(套件))
"""

失败脚本 = """\
从 测试 导入 测试套件, 断言等于
定义 套件 = 测试套件("减法")
套件.start()
尝试
    断言等于(2 - 1, 5)
    套件.record_pass("减法断言")
捕获 错误
    套件.record_fail("减法断言", "5", 文本(错误))
"""

无套件脚本 = "定义 x = 1\n"


def 写文件(目录, 名称: str, 源码: str):
    路径 = 目录 / 名称
    路径.parent.mkdir(parents=True, exist_ok=True)
    路径.write_text(源码, encoding="utf-8")
    return 路径


def test_默认发现文件名模式(tmp_path):
    写文件(tmp_path, "测试加法.道", 通过脚本)
    写文件(tmp_path, "计算_测试.道", 失败脚本)
    写文件(tmp_path, "普通脚本.道", 通过脚本)
    (tmp_path / ".隐藏").mkdir()
    写文件(tmp_path / ".隐藏", "测试隐藏.道", 通过脚本)

    发现 = 发现测试文件(tmp_path)
    assert [p.name for p in 发现] == ["测试加法.道", "计算_测试.道"]
    assert all(p.suffix == ".道" for p in 发现)


def test_自定义模式与单文件发现(tmp_path):
    写文件(tmp_path, "检查_用例.道", 通过脚本)
    写文件(tmp_path, "测试加法.道", 通过脚本)
    assert [p.name for p in 发现测试文件(tmp_path, ("*_用例.道",))] == ["检查_用例.道"]
    assert len(发现测试文件(tmp_path / "测试加法.道")) == 1
    assert 发现测试文件(tmp_path / "不存在.道") == []


def test_不存在目录与非法单文件(tmp_path):
    assert 发现测试文件(tmp_path / "无此目录") == []
    普通文件 = tmp_path / "笔记.txt"
    普通文件.write_text("x", encoding="utf-8")
    assert 发现测试文件(普通文件) == []


def test_默认模式包含两种约定():
    assert "测试*.道" in 默认模式 and "*_测试.道" in 默认模式


def test_执行通过测试文件(tmp_path):
    路径 = 写文件(tmp_path, "测试通过.道", 通过脚本)
    结果 = 执行测试文件(路径)
    assert 结果.成功 is True
    assert 结果.套件数 == 1
    assert 结果.通过 == 1 and 结果.失败 == 0
    assert 结果.错误 == ""


def test_执行失败测试文件(tmp_path):
    路径 = 写文件(tmp_path, "测试失败.道", 失败脚本)
    结果 = 执行测试文件(路径)
    assert 结果.成功 is False
    assert 结果.通过 == 0 and 结果.失败 == 1
    assert len(结果.失败详情) == 1
    assert "减法断言" in 结果.失败详情[0]["名称"]


def test_无套件文件视为失败(tmp_path):
    路径 = 写文件(tmp_path, "测试空.道", 无套件脚本)
    结果 = 执行测试文件(路径)
    assert 结果.成功 is False
    assert "未发现测试套件" in 结果.错误


def test_异常文件被捕获(tmp_path):
    路径 = 写文件(tmp_path, "测试语法错.道", "定义 = ???\n")
    结果 = 执行测试文件(路径)
    assert 结果.成功 is False
    assert 结果.错误 != ""


def test_读取不存在文件(tmp_path):
    结果 = 执行测试文件(tmp_path / "缺失.道")
    assert 结果.成功 is False
    assert "无法读取" in 结果.错误


def test_汇总结果与退出码(tmp_path):
    写文件(tmp_path, "测试通过.道", 通过脚本)
    写文件(tmp_path, "计算_测试.道", 失败脚本)
    汇总 = 运行测试(tmp_path)
    assert len(汇总.文件结果) == 2
    assert 汇总.通过 == 1 and 汇总.失败 == 1
    assert 汇总.退出码 == 1


def test_空目录退出码为2(tmp_path):
    汇总 = 运行测试(tmp_path)
    assert 汇总.文件结果 == []
    assert 汇总.通过 == 0 and 汇总.失败 == 0
    assert 汇总.退出码 == 2


def test_全通过退出码为0(tmp_path):
    写文件(tmp_path, "测试通过.道", 通过脚本)
    汇总 = 运行测试(tmp_path)
    assert 汇总.退出码 == 0


def test_报告包含中文汇总与失败详情(tmp_path):
    写文件(tmp_path, "测试通过.道", 通过脚本)
    写文件(tmp_path, "计算_测试.道", 失败脚本)
    文本 = 生成报告(运行测试(tmp_path))
    assert "道语言测试运行器" in 文本
    assert "测试文件: 2" in 文本
    assert "用例总计: 2，通过: 1，失败: 1" in 文本
    assert "运行结果: 存在失败" in 文本
    assert "减法断言" in 文本


def test_简洁报告隐藏失败详情(tmp_path):
    写文件(tmp_path, "计算_测试.道", 失败脚本)
    文本 = 生成报告(运行测试(tmp_path), 显示详情=False)
    assert "减法断言" not in 文本
    assert "存在失败" in 文本


def test_main命令行成功与失败退出码(tmp_path, capsys):
    写文件(tmp_path, "测试通过.道", 通过脚本)
    assert main([str(tmp_path)]) == 0
    assert "全部通过" in capsys.readouterr().out

    写文件(tmp_path, "计算_测试.道", 失败脚本)
    assert main([str(tmp_path), "--quiet"]) == 1
    assert "存在失败" in capsys.readouterr().out


def test_main无测试退出码(tmp_path, capsys):
    assert main([str(tmp_path)]) == 2
    assert "未发现测试" in capsys.readouterr().out
