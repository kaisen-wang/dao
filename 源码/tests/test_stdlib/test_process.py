"""进程模块测试：覆盖子进程创建、输出捕获、超时、退出码与错误路径。"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.errors import 类型错误, 运行时错误
from dao.stdlib.process import (
    DaoProcess,
    DaoProcessResult,
    _stdlib_启动命令,
    _stdlib_是否运行,
    _stdlib_等待进程,
    _stdlib_运行命令,
    _stdlib_进程退出码,
    _stdlib_进程通信,
    _stdlib_终止进程,
    create_module_env,
)

PYTHON = sys.executable


class Test运行命令:
    def test_捕获标准输出与退出码(self):
        结果 = _stdlib_运行命令(PYTHON, ["-c", "print(123)"])
        assert isinstance(结果, DaoProcessResult)
        assert 结果.退出码 == 0
        assert 结果.标准输出.strip() == "123"
        assert 结果.成功 is True

    def test_非零退出码(self):
        结果 = _stdlib_运行命令(PYTHON, ["-c", "raise SystemExit(7)"])
        assert 结果.退出码 == 7
        assert 结果.成功 is False

    def test_捕获标准错误(self):
        结果 = _stdlib_运行命令(PYTHON, ["-c", "import sys; sys.stderr.write('出错\\n')"])
        assert "出错" in 结果.标准错误

    def test_工作目录(self, tmp_path):
        结果 = _stdlib_运行命令(
            PYTHON, ["-c", "import os; print(os.getcwd())"], 工作目录=str(tmp_path)
        )
        assert os.path.realpath(结果.标准输出.strip()) == os.path.realpath(str(tmp_path))

    def test_命令不存在(self):
        with pytest.raises(运行时错误):
            _stdlib_运行命令("这个命令绝对不存在_xyz_123")

    def test_超时(self):
        with pytest.raises(运行时错误, match="超时"):
            _stdlib_运行命令(PYTHON, ["-c", "import time; time.sleep(3)"], 超时=0.1)

    def test_参数类型校验(self):
        with pytest.raises(类型错误):
            _stdlib_运行命令(123)
        with pytest.raises(类型错误):
            _stdlib_运行命令(PYTHON, "不是列表")
        with pytest.raises(类型错误):
            _stdlib_运行命令(PYTHON, [123])
        with pytest.raises(类型错误):
            _stdlib_运行命令(PYTHON, 工作目录=123)
        with pytest.raises(类型错误):
            _stdlib_运行命令(PYTHON, 超时=-1)


class Test进程生命周期:
    def test_启动与通信(self):
        进程 = _stdlib_启动命令(PYTHON, ["-c", "print(456)"])
        assert isinstance(进程, DaoProcess)
        assert 进程.进程号 > 0
        输出, 错误 = _stdlib_进程通信(进程)
        assert 输出.strip() == "456"
        assert 错误 == ""
        assert _stdlib_等待进程(进程) == 0

    def test_等待与退出码(self):
        进程 = _stdlib_启动命令(PYTHON, ["-c", "raise SystemExit(3)"])
        assert _stdlib_等待进程(进程) == 3
        assert _stdlib_进程退出码(进程) == 3

    def test_是否运行(self):
        进程 = _stdlib_启动命令(PYTHON, ["-c", "import time; time.sleep(0.5)"])
        assert _stdlib_是否运行(进程) is True
        _stdlib_进程通信(进程)
        assert _stdlib_是否运行(进程) is False

    def test_终止进程(self):
        进程 = _stdlib_启动命令(PYTHON, ["-c", "import time; time.sleep(30)"])
        _stdlib_终止进程(进程)
        进程.等待()
        assert _stdlib_是否运行(进程) is False

    def test_进程通信超时(self):
        进程 = _stdlib_启动命令(PYTHON, ["-c", "import time; time.sleep(3)"])
        with pytest.raises(运行时错误, match="超时"):
            _stdlib_进程通信(进程, 超时=0.1)
        _stdlib_终止进程(进程)
        进程.等待()

    def test_非进程对象抛异常(self):
        with pytest.raises(类型错误):
            _stdlib_等待进程("不是进程")
        with pytest.raises(类型错误):
            _stdlib_终止进程(123)
        with pytest.raises(类型错误):
            _stdlib_是否运行(None)
        with pytest.raises(类型错误):
            _stdlib_进程退出码(123)
        with pytest.raises(类型错误):
            _stdlib_进程通信(123)

    def test_启动命令不存在(self):
        with pytest.raises(运行时错误):
            _stdlib_启动命令("这个命令绝对不存在_xyz_123")


class Test进程模块环境:
    def test_导出集合与类型(self):
        env = create_module_env()
        assert "运行命令" in env.values
        assert "进程结果" in env.values
        assert set(env.exports) == set(env.values)
