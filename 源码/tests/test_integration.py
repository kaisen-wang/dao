"""
集成测试：运行 .道 示例文件
============================

确保所有示例程序能够正确解析和执行。
"""

import sys
import os
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from dao.lexer import Lexer
from dao.parser import Parser
from dao.interpreter import Interpreter

EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), '..', 'examples')
MAIN_PY = os.path.join(os.path.dirname(__file__), '..', 'main.py')


def get_example_files():
    """获取所有 .道 示例文件"""
    files = []
    for f in sorted(os.listdir(EXAMPLES_DIR)):
        if f.endswith('.道'):
            files.append(os.path.join(EXAMPLES_DIR, f))
    return files


def run_file(filepath: str) -> tuple[str, int]:
    """运行一个 .道 文件，返回 (输出, 退出码)"""
    with open(filepath, 'r', encoding='utf-8') as f:
        source = f.read()
    tokens = Lexer(source, filepath).tokenize()
    ast = Parser(tokens).parse()
    # 捕获输出
    from io import StringIO
    old_stdout = sys.stdout
    sys.stdout = captured = StringIO()
    try:
        Interpreter().execute(ast)
        output = captured.getvalue()
        return output, 0
    except Exception as e:
        output = captured.getvalue()
        return output + f"\n错误: {e}", 1
    finally:
        sys.stdout = old_stdout


# ========================
# 参数化测试：每个示例文件一个测试用例
# ========================

@pytest.mark.parametrize("filepath", get_example_files(),
                         ids=[os.path.basename(f) for f in get_example_files()])
def test_example_runs_without_error(filepath):
    """示例程序应当能够正常执行（无异常）"""
    output, exit_code = run_file(filepath)
    assert exit_code == 0, f"文件 {filepath} 执行失败:\n{output}"


# ========================
# 逐个示例的输出验证
# ========================

class TestExampleOutputs:
    """验证各示例的关键输出"""

    def test_你好世界(self):
        filepath = os.path.join(EXAMPLES_DIR, '你好世界.道')
        output, _ = run_file(filepath)
        assert "你好，世界！" in output
        assert "欢迎来到道语言！" in output
        assert "你好道" in output

    def test_基础示例(self):
        filepath = os.path.join(EXAMPLES_DIR, '基础示例.道')
        output, _ = run_file(filepath)
        assert "张三" in output
        assert "25" in output
        assert "成年人" in output
        assert "苹果" in output
        assert "7" in output
        assert "捕获到错误" in output
        assert "程序结束" in output

    def test_斐波那契(self):
        filepath = os.path.join(EXAMPLES_DIR, '斐波那契.道')
        output, _ = run_file(filepath)
        lines = [l.strip() for l in output.strip().split('\n') if l.strip()]
        # 前10项：0, 1, 1, 2, 3, 5, 8, 13, 21, 34
        fib_values = ['0', '1', '1', '2', '3', '5', '8', '13', '21', '34']
        for val in fib_values:
            assert val in lines

    def test_面向对象(self):
        filepath = os.path.join(EXAMPLES_DIR, '面向对象.道')
        output, _ = run_file(filepath)
        assert "咪咪，3岁" in output
        assert "白色的咪咪" in output
        assert "旺财，5岁" in output
        assert "喵~" in output
        assert "汪汪!" in output
        assert "小猫是猫？真" in output
        assert "小猫是动物？真" in output

    def test_高阶函数(self):
        filepath = os.path.join(EXAMPLES_DIR, '高阶函数.道')
        output, _ = run_file(filepath)
        assert "[1, 4, 9, 16, 25]" in output
        assert "[2, 4]" in output
        assert "15" in output
        assert "[100, 64, 36, 16, 4]" in output
        assert "优秀学生" in output
        assert "全部及格: 真" in output

    def test_模式匹配(self):
        filepath = os.path.join(EXAMPLES_DIR, '模式匹配.道')
        output, _ = run_file(filepath)
        assert "星期一" in output
        assert "星期日" in output
        assert "优秀" in output
        assert "不及格" in output
        assert "春天" in output
        assert "冬天" in output

    def test_综合示例(self):
        filepath = os.path.join(EXAMPLES_DIR, '综合示例.道')
        output, _ = run_file(filepath)
        assert "图书管理系统" in output
        assert "道德经" in output
        assert "总计: 5 本" in output
        assert "总价值: ¥232" in output
        assert "按价格排序" in output
        assert "程序执行完毕" in output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
