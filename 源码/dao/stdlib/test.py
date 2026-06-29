import time as _time

from ..builtins.callables import BuiltinFunction
from ..environment import Environment
from ..errors import 断言失败, 运行时错误


class DaoTestSuite:
    def __init__(self, name: str):
        self.name = name
        self.tests: list[dict] = []
        self.passed: int = 0
        self.failed: int = 0
        self.failures: list[dict] = []
        self.start_time: float = 0.0
        self.end_time: float = 0.0

    def start(self):
        self.start_time = _time.perf_counter()

    def record_pass(self, name: str):
        self.passed += 1
        self.tests.append({"名称": name, "通过": True})

    def record_fail(self, name: str, expected=None, actual=None):
        self.failed += 1
        self.tests.append({"名称": name, "通过": False})
        self.failures.append({"名称": name, "期望": expected, "实际": actual})

    def elapsed_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return (_time.perf_counter() - self.start_time) * 1000

    def summary(self) -> str:
        total = self.passed + self.failed
        lines = [
            f"测试套件: {self.name}",
            f"总计: {total}, 通过: {self.passed}, 失败: {self.failed}",
            f"耗时: {self.elapsed_ms():.2f} 毫秒",
        ]
        if self.failures:
            lines.append("失败详情:")
            for f in self.failures:
                lines.append(f"  - {f['名称']}: 期望 {f['期望']}, 实际 {f['实际']}")
        return "\n".join(lines)


def _stdlib_断言等于(期望, 实际):
    if 期望 != 实际:
        raise 断言失败(f"断言失败: 期望 {期望}, 实际 {实际}")


def _stdlib_断言不等于(期望, 实际):
    if 期望 == 实际:
        raise 断言失败(f"断言失败: 期望不等于 {期望}, 但两者相等")


def _stdlib_断言为真(值):
    if not 值:
        raise 断言失败(f"断言失败: 期望为真, 实际为 {值}")


def _stdlib_断言为假(值):
    if 值:
        raise 断言失败(f"断言失败: 期望为假, 实际为 {值}")


def _stdlib_断言为空(值):
    if 值:
        raise 断言失败(f"断言失败: 期望为空, 实际为 {值}")


def _stdlib_断言包含(集合, 元素):
    if 元素 not in 集合:
        raise 断言失败(f"断言失败: 期望集合包含 {元素}")


def _stdlib_断言抛出(函数, 异常类型=None):
    try:
        if isinstance(函数, BuiltinFunction):
            函数.call([], {})
        elif callable(函数):
            函数()
        else:
            raise 运行时错误("断言抛出需要函数类型参数")
        raise 断言失败("断言失败: 期望抛出异常, 但未抛出")
    except 断言失败:
        raise
    except Exception:
        pass


def _stdlib_测试套件(名称):
    return DaoTestSuite(名称)


def _stdlib_测试报告(套件):
    if not isinstance(套件, DaoTestSuite):
        raise 运行时错误("测试报告需要测试套件类型参数")
    return 套件.summary()


def create_module_env(interpreter=None) -> Environment:
    env = Environment()
    env.define("断言等于", BuiltinFunction("断言等于", _stdlib_断言等于, 2))
    env.define("断言不等于", BuiltinFunction("断言不等于", _stdlib_断言不等于, 2))
    env.define("断言为真", BuiltinFunction("断言为真", _stdlib_断言为真, 1))
    env.define("断言为假", BuiltinFunction("断言为假", _stdlib_断言为假, 1))
    env.define("断言为空", BuiltinFunction("断言为空", _stdlib_断言为空, 1))
    env.define("断言包含", BuiltinFunction("断言包含", _stdlib_断言包含, 2))
    env.define("断言抛出", BuiltinFunction("断言抛出", _stdlib_断言抛出, -1))
    env.define("测试套件", BuiltinFunction("测试套件", _stdlib_测试套件, 1))
    env.define("测试报告", BuiltinFunction("测试报告", _stdlib_测试报告, 1))
    env.exports = list(env.values.keys())
    return env