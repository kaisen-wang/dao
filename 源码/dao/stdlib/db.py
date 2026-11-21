"""SQLite 数据库标准库模块。

为「道」语言提供轻量的关系型持久化能力，支撑常驻研发 Agent 的
工单/事件存储与崩溃恢复。底层仅使用 Python 标准库 ``sqlite3``。

导出名“连接”返回一个 :class:`DaoConnection`，通过中文方法执行 SQL：:

    定义 数据库 = 数据库库.连接("data/agent.db")
    数据库.执行("CREATE TABLE IF NOT EXISTS 工单 (id INTEGER PRIMARY KEY, 标题 TEXT)")
    数据库.提交()
    定义 行 = 数据库.查询一个("SELECT 标题 FROM 工单 WHERE id = ?", [1])
    数据库.关闭()

所有 SQL 均通过 ``?`` 占位符绑定参数，不拼接字符串，避免注入风险。
"""

import sqlite3
import threading

from ..builtins.callables import BuiltinFunction
from ..environment import Environment
from ..errors import 类型错误, 运行时错误


def _绑定参数(参数):
    """把参数规范为 sqlite3 可绑定的元组（None 表示无参数）。"""
    if 参数 is None:
        return ()
    if isinstance(参数, (list, tuple)):
        return tuple(参数)
    # 单个标量也被当作一个绑定参数，方便道语言直接传入值。
    return (参数,)


def _校验路径(路径):
    if not isinstance(路径, str):
        raise 类型错误("连接需要文本类型路径参数")


def _校验SQL(sql):
    if not isinstance(sql, str):
        raise 类型错误("SQL 语句必须是文本类型")


class DaoConnection:
    """线程安全的 SQLite 连接封装，暴露中文方法供道语言调用。"""

    def __init__(self, 路径: str):
        _校验路径(路径)
        self._路径 = 路径
        self._lock = threading.RLock()
        self._closed = False
        try:
            self._conn = sqlite3.connect(路径, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        except sqlite3.Error as e:
            raise 运行时错误(f"数据库连接失败: {e}") from e

    def _确保打开(self):
        if self._closed:
            raise 运行时错误("数据库连接已关闭")

    def _执行游标(self, sql, 参数=None):
        """内部：在锁内执行 SQL 并返回游标的辅助方法。"""
        self._确保打开()
        _校验SQL(sql)
        try:
            return self._conn.execute(sql, _绑定参数(参数))
        except sqlite3.Error as e:
            raise 运行时错误(f"数据库执行失败: {e}") from e

    def 执行(self, sql: str, 参数=None) -> int:
        """执行 INSERT/UPDATE/DELETE/CREATE 等语句，返回受影响行数。"""
        with self._lock:
            cur = self._执行游标(sql, 参数)
            return cur.rowcount

    def 查询(self, sql: str, 参数=None) -> list:
        """执行查询并返回全部行，每行是一个“列名 → 值”的字典。"""
        with self._lock:
            cur = self._执行游标(sql, 参数)
            return [dict(row) for row in cur.fetchall()]

    def 查询一个(self, sql: str, 参数=None):
        """执行查询并返回首行字典；无结果时返回 None。"""
        with self._lock:
            cur = self._执行游标(sql, 参数)
            row = cur.fetchone()
            return dict(row) if row is not None else None

    def 提交(self) -> None:
        """提交当前事务。"""
        with self._lock:
            self._确保打开()
            try:
                self._conn.commit()
            except sqlite3.Error as e:
                raise 运行时错误(f"数据库提交失败: {e}") from e

    def 回滚(self) -> None:
        """回滚当前事务。"""
        with self._lock:
            self._确保打开()
            try:
                self._conn.rollback()
            except sqlite3.Error as e:
                raise 运行时错误(f"数据库回滚失败: {e}") from e

    def 开启WAL(self):
        """开启 Write-Ahead Logging 模式，返回当前 journal_mode 字符串。"""
        with self._lock:
            cur = self._执行游标("PRAGMA journal_mode=WAL")
            row = cur.fetchone()
            return row[0] if row is not None else None

    def 关闭(self) -> None:
        """关闭连接；重复关闭安全。关闭后其他操作将抛运行时错误。"""
        with self._lock:
            if self._closed:
                return
            try:
                self._conn.close()
            except sqlite3.Error as e:
                raise 运行时错误(f"数据库关闭失败: {e}") from e
            finally:
                self._closed = True

    def 最后行ID(self) -> int:
        """返回最近一次 INSERT 的行 ID（无插入时为 0）。"""
        with self._lock:
            cur = self._执行游标("SELECT last_insert_rowid()")
            return int(cur.fetchone()[0])


def _stdlib_连接(路径: str) -> DaoConnection:
    """打开或新建指定路径的 SQLite 数据库，返回一个连接对象。"""
    return DaoConnection(路径)


# 模块级单例：docgen 依赖其名称/参数个数/docstring 等元数据稳定。
_连接_BUILTIN = BuiltinFunction("连接", _stdlib_连接, 1)


def create_module_env(interpreter=None) -> Environment:
    """创建数据库模块的导出环境。"""
    env = Environment()
    env.define("连接", _连接_BUILTIN)
    env.exports = list(env.values.keys())
    return env
