"""
模块系统测试 - 导入和导出
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dao.lexer import Lexer
from dao.parser import Parser
from dao.interpreter import Interpreter
import io
from contextlib import redirect_stdout
import tempfile
import shutil


def run_with_module(source: str, module_name: str, module_code: str) -> str:
    """运行带临时模块的源代码"""
    # 创建临时目录
    temp_dir = tempfile.mkdtemp()

    try:
        # 创建模块目录
        module_path = module_name.replace(".", os.sep) + ".道"
        module_file = os.path.join(temp_dir, module_path)
        module_dir = os.path.dirname(module_file)

        os.makedirs(module_dir, exist_ok=True)

        # 写入模块文件
        with open(module_file, "w", encoding="utf-8") as f:
            f.write(module_code)

        # 切换到临时目录运行主代码
        original_cwd = os.getcwd()
        os.chdir(temp_dir)

        try:
            lexer = Lexer(source)
            tokens = lexer.tokenize()
            parser = Parser(tokens)
            ast = parser.parse()
            interpreter = Interpreter()

            output = io.StringIO()
            with redirect_stdout(output):
                interpreter.execute(ast)

            return output.getvalue()
        finally:
            os.chdir(original_cwd)
    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir)


class TestExport:
    """测试导出功能"""

    def test_export_single(self):
        """测试导出单个变量"""
        module_code = """定义 x = 42
导出 x
"""
        source = """导入 my_module
打印(my_module.x)
"""
        result = run_with_module(source, "my_module", module_code)
        assert "42" in result

    def test_export_multiple(self):
        """测试导出多个变量"""
        module_code = """定义 x = 1
定义 y = 2
定义 z = 3
导出 {x, y, z}
"""
        source = """导入 my_module
打印(my_module.x)
打印(my_module.y)
打印(my_module.z)
"""
        result = run_with_module(source, "my_module", module_code)
        assert "1" in result
        assert "2" in result
        assert "3" in result

    def test_export_filters_non_exported(self):
        """测试只有导出的变量才能被访问"""
        module_code = """定义 public = "可见"
定义 private = "隐藏"
导出 public
"""
        source = """导入 my_module
打印(my_module.public)
"""
        result = run_with_module(source, "my_module", module_code)
        assert "可见" in result
        assert "隐藏" not in result


class TestSelectiveImport:
    """测试选择性导入"""

    def test_from_import_single(self):
        """测试从模块导入单个变量"""
        module_code = """定义 x = 42
定义 y = 100
导出 {x, y}
"""
        source = """从 my_module 导入 x
打印(x)
"""
        result = run_with_module(source, "my_module", module_code)
        assert "42" in result

    def test_from_import_multiple(self):
        """测试从模块导入多个变量"""
        module_code = """定义 a = 1
定义 b = 2
定义 c = 3
导出 {a, b, c}
"""
        source = """从 my_module 导入 {a, b, c}
打印(a)
打印(b)
打印(c)
"""
        result = run_with_module(source, "my_module", module_code)
        assert "1" in result
        assert "2" in result
        assert "3" in result

    def test_from_import_error_not_exported(self):
        """测试导入未导出的变量时报错"""
        module_code = """定义 x = 1
导出 x
"""
        source = """从 my_module 导入 y
"""
        try:
            run_with_module(source, "my_module", module_code)
            assert False, "应该抛出运行时错误"
        except Exception as e:
            assert "没有导出" in str(e) or "y" in str(e)

    def test_from_import_with_functions(self):
        """测试选择性导入函数"""
        module_code = """函数 加法(甲, 乙)
    返回 甲 + 乙

函数 乘法(甲, 乙)
    返回 甲 * 乙

导出 {加法, 乘法}
"""
        source = """从 math 导入 {加法, 乘法}
打印(加法(2, 3))
打印(乘法(4, 5))
"""
        result = run_with_module(source, "math", module_code)
        assert "5" in result
        assert "20" in result


class TestModuleWithExport:
    """测试导出和选择性导入的组合"""

    def test_module_with_functions_and_data(self):
        """测试模块同时导出函数和数据"""
        module_code = """定义 PI = 3.14159

函数 圆面积(半径)
    返回 PI * 半径 * 半径

导出 {PI, 圆面积}
"""
        source = """从 geometry 导入 {PI, 圆面积}
定义 面积 = 圆面积(5)
打印(PI)
打印(面积)
"""
        result = run_with_module(source, "geometry", module_code)
        assert "3.14159" in result
        assert "78.53975" in result

    def test_nested_module_import(self):
        """测试嵌套模块导入"""
        # 创建嵌套模块结构
        pass  # 这个测试需要更复杂的文件系统操作


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
