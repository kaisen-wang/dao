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
    return run_with_modules(source, {module_name: module_code})


def run_with_modules(source: str, modules: dict[str, str]) -> str:
    """运行带多个临时模块的源代码

    参数:
        source: 主程序源代码
        modules: 模块路径到模块代码的映射，如 {"工具.数学": "导出 函数 加(...)..."}
    """
    temp_dir = tempfile.mkdtemp()

    try:
        for module_path, module_code in modules.items():
            file_path = module_path.replace(".", os.sep) + ".道"
            module_file = os.path.join(temp_dir, file_path)
            module_dir = os.path.dirname(module_file)

            os.makedirs(module_dir, exist_ok=True)

            with open(module_file, "w", encoding="utf-8") as f:
                f.write(module_code)

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
导出 x, y, z
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
导出 x, y
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
导出 a, b, c
"""
        source = """从 my_module 导入 a, b, c
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

导出 加法, 乘法
"""
        source = """从 math 导入 加法, 乘法
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

导出 PI, 圆面积
"""
        source = """从 geometry 导入 PI, 圆面积
定义 面积 = 圆面积(5)
打印(PI)
打印(面积)
"""
        result = run_with_module(source, "geometry", module_code)
        assert "3.14159" in result
        assert "78.53975" in result

    def test_nested_module_import(self):
        """测试嵌套模块导入"""
        modules = {
            "工具.数学": """导出 函数 加(甲, 乙)
    返回 甲 + 乙
""",
            "工具.文本": """导出 函数 问候(名字)
    返回 "你好, " + 名字
""",
        }
        source = """从 工具.数学 导入 加
从 工具.文本 导入 问候
打印(加(1, 2))
打印(问候("世界"))
"""
        result = run_with_modules(source, modules)
        assert "3" in result
        assert "你好, 世界" in result


class TestExportDefinition:
    """测试逐项导出语法（导出 函数/常量/类型）"""

    def test_export_function(self):
        """测试导出函数定义"""
        module_code = """导出 函数 加(甲, 乙)
    返回 甲 + 乙
"""
        source = """从 my_module 导入 加
打印(加(1, 2))
"""
        result = run_with_module(source, "my_module", module_code)
        assert "3" in result

    def test_export_constant(self):
        """测试导出常量定义"""
        module_code = """导出 常量 圆周率 = 3.14
"""
        source = """从 my_module 导入 圆周率
打印(圆周率)
"""
        result = run_with_module(source, "my_module", module_code)
        assert "3.14" in result

    def test_export_variable(self):
        """测试导出变量定义"""
        module_code = """导出 定义 x = 42
"""
        source = """从 my_module 导入 x
打印(x)
"""
        result = run_with_module(source, "my_module", module_code)
        assert "42" in result

    def test_export_class(self):
        """测试导出类型定义"""
        module_code = """导出 类型 向量
    初始化(x, y)
        本对象.x = x
        本对象.y = y
"""
        source = """从 my_module 导入 向量
定义 v = 向量(1, 2)
打印(v.x)
打印(v.y)
"""
        result = run_with_module(source, "my_module", module_code)
        assert "1" in result
        assert "2" in result

    def test_export_mixed_with_concentrated(self):
        """测试逐项导出与集中导出混合使用"""
        module_code = """导出 函数 加(甲, 乙)
    返回 甲 + 乙

定义 私有值 = 100
定义 公开值 = 200
导出 公开值
"""
        source = """导入 my_module
打印(my_module.加(3, 4))
打印(my_module.公开值)
"""
        result = run_with_module(source, "my_module", module_code)
        assert "7" in result
        assert "200" in result
        assert "100" not in result


class TestRenamedImport:
    """测试重命名导入（从 模块 导入 名称 作为 别名）"""

    def test_single_renamed_import(self):
        """测试单个重命名导入"""
        module_code = """导出 函数 加(甲, 乙)
    返回 甲 + 乙
"""
        source = """从 my_module 导入 加 作为 数学加法
打印(数学加法(1, 2))
"""
        result = run_with_module(source, "my_module", module_code)
        assert "3" in result

    def test_mixed_renamed_import(self):
        """测试混合重命名导入（部分有别名，部分无）"""
        module_code = """定义 x = 10
定义 y = 20
导出 x, y
"""
        source = """从 my_module 导入 x 作为 甲, y
打印(甲)
打印(y)
"""
        result = run_with_module(source, "my_module", module_code)
        assert "10" in result
        assert "20" in result

    def test_renamed_import_avoids_conflict(self):
        """测试重命名导入避免命名冲突"""
        module_code = """导出 函数 处理(数据)
    返回 数据 + 1
"""
        source = """定义 处理 = "原始值"
从 my_module 导入 处理 作为 模块处理
打印(处理)
打印(模块处理(5))
"""
        result = run_with_module(source, "my_module", module_code)
        assert "原始值" in result
        assert "6" in result


class TestModuleCache:
    """测试模块缓存（重复导入只执行一次）"""

    def test_module_init_once(self):
        """测试模块初始化代码只执行一次"""
        module_code = """定义 计数 = 0
计数 = 计数 + 1
导出 计数
"""
        source = """从 my_module 导入 计数
打印(计数)
从 my_module 导入 计数 作为 c2
打印(c2)
"""
        result = run_with_module(source, "my_module", module_code)
        assert "1" in result

    def test_module_import_twice_same_result(self):
        """测试多次导入返回相同结果"""
        module_code = """导出 函数 获取值()
    返回 42
"""
        source = """导入 my_module
从 my_module 导入 获取值
打印(my_module.获取值())
打印(获取值())
"""
        result = run_with_module(source, "my_module", module_code)
        assert result.count("42") == 2


class TestCircularDependency:
    """测试循环依赖检测"""

    def test_direct_circular_import(self):
        """测试直接循环导入检测"""
        modules = {
            "模块甲": """导入 模块乙
导出 函数 甲函数()
    返回 1
""",
            "模块乙": """导入 模块甲
导出 函数 乙函数()
    返回 2
""",
        }
        source = """导入 模块甲
"""
        try:
            run_with_modules(source, modules)
            assert False, "应该抛出循环导入错误"
        except Exception as e:
            assert "循环导入" in str(e)


class TestConditionalImport:
    """测试条件导入（如果/否则 + 导入 组合）"""

    def test_import_in_if_block(self):
        """测试在条件块内导入"""
        modules = {
            "模块甲": """导出 定义 值 = "来自模块甲"
""",
        }
        source = """定义 条件 = 1
如果 条件 == 1
    从 模块甲 导入 值
    打印(值)
"""
        result = run_with_modules(source, modules)
        assert "来自模块甲" in result


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
