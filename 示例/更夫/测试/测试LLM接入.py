"""更夫 Nightwatch 回归测试的 pytest 入口（薄壳）。

测试逻辑全部用道语言编写，见同目录的 `测试LLM接入.道`。
本文件只负责用当前解释器运行该道语言测试脚本，并把套件报告回显给 pytest，
从而保留既有 pytest / CI 集成；不在此处重复实现任何断言。
"""

import os
import subprocess
import sys
from pathlib import Path

更夫目录 = Path(__file__).resolve().parents[1]
项目根 = 更夫目录.parents[1]
解释器 = 项目根 / "源码" / "main.py"
测试脚本 = "测试/测试LLM接入.道"


def test_道语言测试套件():
    """运行道语言测试套件：13 个用例全部通过才算成功。"""
    环境 = os.environ.copy()
    环境["PYTHONPATH"] = str(项目根 / "源码")
    结果 = subprocess.run(
        [sys.executable, str(解释器), 测试脚本],
        check=False,
        cwd=str(更夫目录),
        env=环境,
        capture_output=True,
        text=True,
        timeout=180,
    )
    输出 = 结果.stdout + 结果.stderr
    assert "总计: 13, 通过: 13, 失败: 0" in 输出, f"道语言测试套件未全部通过：\n{输出}"
    assert 结果.returncode == 0, f"道语言测试套件退出码非 0：\n{输出}"
