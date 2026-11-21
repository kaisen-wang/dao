import os
import sys
import tempfile
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from dao.errors import 类型错误, 运行时错误
from dao.stdlib.db import DaoConnection, _stdlib_连接, create_module_env


def _新库(tmpdir, 名字="test.db"):
    return os.path.join(tmpdir, 名字)


class TestDatabaseBasic:
    def test_建表插入查询(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = _stdlib_连接(_新库(tmpdir))
            try:
                conn.执行("CREATE TABLE 工单 (id INTEGER PRIMARY KEY, 标题 TEXT)")
                assert conn.执行("INSERT INTO 工单 (标题) VALUES (?)", ["修复崩溃"]) == 1
                assert conn.提交() is None
                rows = conn.查询("SELECT id, 标题 FROM 工单")
                assert len(rows) == 1
                assert rows[0] == {"id": 1, "标题": "修复崩溃"}
            finally:
                conn.关闭()

    def test_参数绑定防注入(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = _stdlib_连接(_新库(tmpdir))
            try:
                conn.执行("CREATE TABLE 笔记 (内容 TEXT)")
                注入文本 = "O'Reilly'); DROP TABLE 笔记; --"
                conn.执行("INSERT INTO 笔记 (内容) VALUES (?)", [注入文本])
                conn.提交()
                rows = conn.查询("SELECT 内容 FROM 笔记")
                assert len(rows) == 1
                assert rows[0]["内容"] == 注入文本
                # 表仍然存在，说明注入未生效
                assert conn.查询("SELECT COUNT(*) AS n FROM 笔记")[0]["n"] == 1
            finally:
                conn.关闭()

    def test_查询一个_有结果与无结果(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = _stdlib_连接(_新库(tmpdir))
            try:
                conn.执行("CREATE TABLE t (id INTEGER, v TEXT)")
                conn.执行("INSERT INTO t VALUES (?, ?)", (1, "甲"))
                conn.提交()
                row = conn.查询一个("SELECT v FROM t WHERE id = ?", [1])
                assert isinstance(row, dict)
                assert row == {"v": "甲"}
                assert conn.查询一个("SELECT v FROM t WHERE id = ?", [999]) is None
            finally:
                conn.关闭()

    def test_提交与回滚(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _新库(tmpdir)
            conn = _stdlib_连接(path)
            try:
                conn.执行("CREATE TABLE t (v TEXT)")
                conn.提交()

                conn.执行("INSERT INTO t VALUES (?)", ["已提交"])
                conn.提交()
                assert conn.查询("SELECT v FROM t") == [{"v": "已提交"}]

                conn.执行("INSERT INTO t VALUES (?)", ["要回滚"])
                conn.回滚()
                assert conn.查询("SELECT v FROM t") == [{"v": "已提交"}]
            finally:
                conn.关闭()

            # 用新连接确认回滚确实未落盘
            conn2 = _stdlib_连接(path)
            try:
                assert conn2.查询("SELECT v FROM t") == [{"v": "已提交"}]
            finally:
                conn2.关闭()

    def test_开启WAL(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = _stdlib_连接(_新库(tmpdir))
            try:
                mode = conn.开启WAL()
                assert str(mode).lower() == "wal"
                assert conn.查询("PRAGMA journal_mode")[0]["journal_mode"] == "wal"
            finally:
                conn.关闭()

    def test_最后行ID(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = _stdlib_连接(_新库(tmpdir))
            try:
                conn.执行("CREATE TABLE t (id INTEGER PRIMARY KEY AUTOINCREMENT, v TEXT)")
                assert conn.最后行ID() == 0
                conn.执行("INSERT INTO t (v) VALUES (?)", ["a"])
                assert conn.最后行ID() == 1
                conn.执行("INSERT INTO t (v) VALUES (?)", ["b"])
                assert conn.最后行ID() == 2
            finally:
                conn.关闭()


class TestDatabaseErrors:
    def test_关闭后查询抛运行时错误(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = _stdlib_连接(_新库(tmpdir))
            conn.执行("CREATE TABLE t (v TEXT)")
            conn.关闭()
            with pytest.raises(运行时错误, match="数据库连接已关闭"):
                conn.查询("SELECT * FROM t")
            # 重复关闭安全
            conn.关闭()

    def test_非法SQL抛运行时错误(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = _stdlib_连接(_新库(tmpdir))
            try:
                with pytest.raises(运行时错误, match="数据库执行失败"):
                    conn.执行("THIS IS NOT SQL")
            finally:
                conn.关闭()

    def test_路径类型错误(self):
        with pytest.raises(类型错误):
            _stdlib_连接(123)


class TestDatabaseConcurrency:
    def test_多连接并发写入(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _新库(tmpdir)
            主连接 = _stdlib_连接(path)
            主连接.执行("CREATE TABLE 事件 (id INTEGER PRIMARY KEY, 内容 TEXT)")
            主连接.开启WAL()
            主连接.提交()
            主连接.关闭()

            错误列表 = []

            def 工作(线程号):
                try:
                    conn = _stdlib_连接(path)
                    try:
                        for i in range(10):
                            conn.执行(
                                "INSERT INTO 事件 (内容) VALUES (?)",
                                [f"线程{线程号}-{i}"],
                            )
                            conn.提交()
                    finally:
                        conn.关闭()
                except Exception as e:  # noqa: BLE001 - 测试需收集所有线程异常
                    错误列表.append(e)

            线程们 = [threading.Thread(target=工作, args=(n,)) for n in range(4)]
            for t in 线程们:
                t.start()
            for t in 线程们:
                t.join()

            assert not 错误列表, f"并发写入出现异常: {错误列表}"

            校验连接 = _stdlib_连接(path)
            try:
                assert 校验连接.查询("SELECT COUNT(*) AS n FROM 事件")[0]["n"] == 40
            finally:
                校验连接.关闭()

    def test_单连接多线程共享(self):
        """验证 RLock 保护同一连接被多线程复用时不崩。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = _stdlib_连接(_新库(tmpdir))
            conn.执行("CREATE TABLE t (v TEXT)")
            conn.提交()

            错误列表 = []

            def 工作(线程号):
                try:
                    for i in range(20):
                        conn.执行("INSERT INTO t VALUES (?)", [f"{线程号}-{i}"])
                    conn.提交()
                except Exception as e:  # noqa: BLE001 - 测试需收集所有线程异常
                    错误列表.append(e)

            线程们 = [threading.Thread(target=工作, args=(n,)) for n in range(4)]
            for t in 线程们:
                t.start()
            for t in 线程们:
                t.join()

            assert not 错误列表, f"多线程共享连接出现异常: {错误列表}"
            assert conn.查询("SELECT COUNT(*) AS n FROM t")[0]["n"] == 80
            conn.关闭()


class TestDatabaseModuleEnv:
    def test_create_module_env_导出(self):
        env = create_module_env()
        assert env.exports == ["连接"]
        assert list(env.values.keys()) == ["连接"]
        函数 = env.values["连接"]
        assert 函数.name == "连接"
        assert 函数.param_count == 1
        assert 函数.func is _stdlib_连接

    def test_重复调用元数据稳定(self):
        env1 = create_module_env()
        env2 = create_module_env()
        f1, f2 = env1.values["连接"], env2.values["连接"]
        assert (f1.name, f1.param_count, f1.func) == (f2.name, f2.param_count, f2.func)
        assert f1 is f2  # 模块级单例，元数据完全相同
        assert f1.func.__doc__ == f2.func.__doc__
        assert "打开或新建" in (f1.func.__doc__ or "")

    def test_导出函数可建连(self):
        env = create_module_env()
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = env.values["连接"].call([_新库(tmpdir)], {})
            assert isinstance(conn, DaoConnection)
            conn.关闭()
