"""类型检查器：阻断式诊断、泛型、别名与跨模块检查。"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.lexer import Lexer
from dao.parser import Parser
from dao.types.checker import TypeInferenceEngine, TypeErrorReport


def check_source(source: str, base_dir: str | None = None) -> list[TypeErrorReport]:
    ast = Parser(Lexer(source).tokenize()).parse()
    return TypeInferenceEngine(base_dir=base_dir).check(ast)


class TestTypeDiagnostics:
    def test_mismatch_report_contains_chinese_message_and_position(self):
        reports = check_source("\n定义 x: 文本 = 42\n")
        assert len(reports) == 1
        report = reports[0]
        assert isinstance(report, TypeErrorReport)
        assert "变量 'x'" in report.message
        assert "文本" in report.message and "数值" in report.message
        assert report.line == 2
        assert report.column == 1
        assert "行 2" in str(report) and "列 1" in str(report)

    def test_unknown_combination_is_reported(self):
        # 函数类型注解与数值字面量属于未知/不兼容组合，必须报错而不是放行。
        reports = check_source("定义 f: 函数(数值) -> 数值 = 42\n")
        assert len(reports) == 1
        assert "函数" in reports[0].message

    def test_unannotated_dynamic_usage_has_no_report(self):
        # 没有注解的合法动态用法应保持兼容，不误报。
        reports = check_source(
            "定义 x = 42\nx = \"你好\"\n定义 y = [1, \"a\", 真]\n"
        )
        assert reports == []

    def test_bare_container_annotation_accepts_any_elements(self):
        reports = check_source("定义 x: 列表 = [1, \"a\", 真]\n")
        assert reports == []

    def test_multiple_reports_keep_source_order(self):
        reports = check_source(
            "定义 a: 文本 = 42\n定义 b: 数值 = \"x\"\n"
        )
        assert len(reports) == 2
        assert "a" in reports[0].message
        assert "b" in reports[1].message
        assert reports[0].line < reports[1].line

    def test_assignment_to_annotated_variable_is_checked(self):
        reports = check_source("定义 x: 数值 = 1\nx = \"错误\"\n")
        assert len(reports) == 1
        assert "不能赋予" in reports[0].message


class TestGenericTypeChecking:
    def test_list_element_type_match(self):
        reports = check_source("定义 x: 列表[数值] = [1, 2, 3]\n")
        assert reports == []

    def test_list_element_type_mismatch(self):
        reports = check_source("定义 x: 列表[数值] = [\"a\", \"b\"]\n")
        assert len(reports) == 1
        assert "列表[数值]" in reports[0].message
        assert "列表[文本]" in reports[0].message

    def test_dict_key_value_types_match(self):
        reports = check_source("定义 x: 字典[文本, 数值] = {\"a\": 1}\n")
        assert reports == []

    def test_dict_key_value_types_mismatch(self):
        reports = check_source("定义 x: 字典[文本, 数值] = {1: \"a\"}\n")
        assert len(reports) == 1
        assert "字典[文本, 数值]" in reports[0].message

    def test_set_element_type_mismatch(self):
        reports = check_source("定义 x: 集合[数值] = {\"a\"}\n")
        assert len(reports) == 1
        assert "集合[数值]" in reports[0].message

    def test_optional_generic_accepts_null(self):
        reports = check_source("定义 x: 可选[数值] = 空\n")
        assert reports == []

    def test_optional_generic_rejects_wrong_element(self):
        reports = check_source("定义 x: 可选[数值] = \"错误\"\n")
        assert len(reports) == 1
        assert "可选[数值]" in reports[0].message

    def test_optional_union_syntax(self):
        assert check_source("定义 x: 文本 | 空 = 空\n") == []
        assert len(check_source("定义 x: 文本 | 空 = 42\n")) == 1

    def test_union_rejects_unlisted_type(self):
        reports = check_source("定义 x: 文本 | 数值 = 真\n")
        assert len(reports) == 1
        assert "文本 | 数值" in reports[0].message

    def test_generic_container_name_mismatch(self):
        reports = check_source("定义 x: 列表[数值] = {1, 2}\n")
        assert len(reports) == 1
        assert "列表[数值]" in reports[0].message


class TestAliasIntegration:
    def test_alias_is_resolved_in_variable_annotation(self):
        reports = check_source(
            "类型别名 ID = 数值\n定义 x: ID = 42\n定义 y: ID = \"错误\"\n"
        )
        assert len(reports) == 1
        assert "数值" in reports[0].message
        assert "文本" in reports[0].message

    def test_alias_cycle_reports_chinese_error(self):
        reports = check_source(
            "类型别名 A = B\n类型别名 B = A\n"
        )
        assert len(reports) == 1
        assert "循环" in reports[0].message
        assert "类型别名" in reports[0].message
        assert reports[0].line == 2

    def test_alias_inside_generic_argument(self):
        reports = check_source(
            "类型别名 ID = 数值\n定义 x: 列表[ID] = [\"错误\"]\n"
        )
        assert len(reports) == 1
        assert "列表[数值]" in reports[0].message


class TestFunctionCallChecking:
    def test_call_argument_type_checked(self):
        reports = check_source(
            "函数 f(x: 数值) -> 数值\n  返回 x + 1\n\n定义 y = f(\"错误\")\n"
        )
        assert len(reports) == 1
        assert "第 1 个参数" in reports[0].message

    def test_call_argument_count_checked(self):
        reports = check_source(
            "函数 f(x: 数值) -> 数值\n  返回 x + 1\n\n定义 y = f(1, 2)\n"
        )
        assert len(reports) == 1
        assert "参数" in reports[0].message

    def test_call_with_correct_signature_has_no_report(self):
        reports = check_source(
            "函数 f(x: 数值) -> 数值\n  返回 x + 1\n\n定义 y = f(2)\n"
        )
        assert reports == []


class TestCrossModuleChecking:
    def test_import_unknown_name_is_reported(self, tmp_path):
        package = tmp_path / "工具"
        package.mkdir()
        (package / "数学.道").write_text(
            "导出 加\n函数 加(x: 数值, y: 数值) -> 数值\n  返回 x + y\n",
            encoding="utf-8",
        )
        reports = check_source(
            "从 工具.数学 导入 不存在\n", base_dir=str(tmp_path)
        )
        assert len(reports) == 1
        assert "不存在" in reports[0].message
        assert "没有导出" in reports[0].message

    def test_import_signature_is_checked(self, tmp_path):
        package = tmp_path / "工具"
        package.mkdir()
        (package / "数学.道").write_text(
            "导出 加\n函数 加(x: 数值, y: 数值) -> 数值\n  返回 x + y\n",
            encoding="utf-8",
        )
        reports = check_source(
            "从 工具.数学 导入 加\n定义 r = 加(\"错误\", 2)\n",
            base_dir=str(tmp_path),
        )
        assert len(reports) == 1
        assert "加" in reports[0].message
        assert "数值" in reports[0].message

    def test_import_valid_signature_has_no_report(self, tmp_path):
        package = tmp_path / "工具"
        package.mkdir()
        (package / "数学.道").write_text(
            "导出 加\n函数 加(x: 数值, y: 数值) -> 数值\n  返回 x + y\n",
            encoding="utf-8",
        )
        reports = check_source(
            "从 工具.数学 导入 加\n定义 r = 加(1, 2)\n",
            base_dir=str(tmp_path),
        )
        assert reports == []
