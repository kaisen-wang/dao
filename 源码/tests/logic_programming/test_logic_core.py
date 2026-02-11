"""
逻辑编程核心功能测试
====================

测试知识库、统一化、回溯等核心功能。
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

import pytest
from dao.logic.core import LogicVariable, LogicAtom, LogicStruct, KnowledgeBase, Substitution, normalize_term
from dao.logic.unification import unify, apply_substitution, occurs_check, is_unifiable
from dao.logic.exceptions import UnificationError as 统一化错误, CircularRuleError as 循环规则错误


class TestLogicVariable:
    """测试逻辑变量类"""

    def test_variable_creation(self):
        """测试变量创建"""
        var = LogicVariable("?x")
        assert var.name == "?x"
        assert not var.is_bound()
        assert var.bound_to is None

    def test_variable_bind_unbind(self):
        """测试变量绑定和解除绑定"""
        var = LogicVariable("?x")

        # 绑定
        var.bind("张三")
        assert var.is_bound()
        assert var.bound_to == "张三"

        # 解除绑定
        var.unbind()
        assert not var.is_bound()
        assert var.bound_to is None

    def test_variable_hash_and_equality(self):
        """测试变量哈希和相等性"""
        var1 = LogicVariable("?x")
        var2 = LogicVariable("?x")
        var3 = LogicVariable("?y")

        # 相同名字的变量相等
        assert var1 == var2
        assert hash(var1) == hash(var2)

        # 不同名字的变量不等
        assert var1 != var3
        assert hash(var1) != hash(var3)

    def test_variable_repr(self):
        """测试变量字符串表示"""
        var = LogicVariable("?x")
        assert repr(var) == "?x"

        var.bind("张三")
        assert repr(var) == "?x='张三'"

    def test_invalid_variable_name(self):
        """测试无效的变量名"""
        with pytest.raises(ValueError):
            LogicVariable("x")  # 必须以?开头


class TestLogicAtom:
    """测试逻辑原子类"""

    def test_atom_creation(self):
        """测试原子创建"""
        atom = LogicAtom("张三")
        assert atom.value == "张三"

    def test_atom_equality(self):
        """测试原子相等性"""
        atom1 = LogicAtom("张三")
        atom2 = LogicAtom("张三")
        atom3 = LogicAtom("李四")

        assert atom1 == atom2
        assert atom1 != atom3

    def test_atom_hash(self):
        """测试原子哈希"""
        atom1 = LogicAtom("张三")
        atom2 = LogicAtom("张三")

        assert hash(atom1) == hash(atom2)


class TestLogicStruct:
    """测试逻辑结构类"""

    def test_struct_creation(self):
        """测试结构创建"""
        struct = LogicStruct("父母", ("张三", "小明"))
        assert struct.predicate == "父母"
        assert struct.args == ("张三", "小明")
        assert struct.arity() == 2

    def test_struct_equality(self):
        """测试结构相等性"""
        struct1 = LogicStruct("父母", ("张三", "小明"))
        struct2 = LogicStruct("父母", ("张三", "小明"))
        struct3 = LogicStruct("父母", ("李四", "小红"))

        assert struct1 == struct2
        assert struct1 != struct3

    def test_struct_repr(self):
        """测试结构字符串表示"""
        struct = LogicStruct("父母", ("张三", "小明"))
        assert repr(struct) == "父母('张三', '小明')"

    def test_struct_with_variables(self):
        """测试包含变量的结构"""
        x = LogicVariable("?x")
        struct = LogicStruct("父母", (x, "小明"))
        assert struct.predicate == "父母"
        assert struct.args[1] == "小明"


class TestOccursCheck:
    """测试发生检查"""

    def test_occurs_in_variable(self):
        """测试变量出现在变量中"""
        x = LogicVariable("?x")
        y = LogicVariable("?y")

        assert not occurs_check(x, y)
        assert occurs_check(x, x)

    def test_occurs_in_struct(self):
        """测试变量出现在结构中"""
        x = LogicVariable("?x")
        struct = LogicStruct("父母", (x, "小明"))

        assert occurs_check(x, struct)

        y = LogicVariable("?y")
        assert not occurs_check(y, struct)

    def test_occurs_in_nested_struct(self):
        """测试变量出现在嵌套结构中"""
        x = LogicVariable("?x")
        inner = LogicStruct("关系", (x,))
        outer = LogicStruct("外层", (inner,))

        assert occurs_check(x, outer)

    def test_no_occurs_in_atom(self):
        """测试变量不出现在原子中"""
        x = LogicVariable("?x")
        atom = LogicAtom("张三")

        assert not occurs_check(x, atom)


class TestUnification:
    """测试统一化"""

    def test_unify_atom_atom_same(self):
        """测试统一化相同的原子"""
        atom1 = LogicAtom("张三")
        atom2 = LogicAtom("张三")

        subst = unify(atom1, atom2)
        assert subst is not None

    def test_unify_atom_atom_different(self):
        """测试统一化不同的原子（失败）"""
        atom1 = LogicAtom("张三")
        atom2 = LogicAtom("李四")

        with pytest.raises(统一化错误):
            unify(atom1, atom2)

    def test_unify_variable_atom(self):
        """测试统一化变量和原子"""
        x = LogicVariable("?x")
        atom = LogicAtom("张三")

        subst = unify(x, atom)
        assert subst is not None
        assert subst.get_value(x) == atom

    def test_unify_atom_variable(self):
        """测试统一化原子和变量（对称）"""
        x = LogicVariable("?x")
        atom = LogicAtom("张三")

        subst = unify(atom, x)
        assert subst is not None
        assert subst.get_value(x) == atom

    def test_unify_variable_variable(self):
        """测试统一化两个变量"""
        x = LogicVariable("?x")
        y = LogicVariable("?y")

        subst = unify(x, y)
        assert subst is not None
        # 绑定应该被记录

    def test_unify_struct_same_predicate(self):
        """测试统一化相同谓词的结构"""
        x = LogicVariable("?x")
        y = LogicVariable("?y")

        struct1 = LogicStruct("父母", (x, "小明"))
        struct2 = LogicStruct("父母", ("张三", y))

        subst = unify(struct1, struct2)
        assert subst is not None
        assert subst.get_value(x).value == "张三"
        assert subst.get_value(y).value == "小明"

    def test_unify_struct_different_predicate(self):
        """测试统一化不同谓词的结构（失败）"""
        struct1 = LogicStruct("父母", ("张三", "小明"))
        struct2 = LogicStruct("子女", ("张三", "小明"))

        with pytest.raises(统一化错误):
            unify(struct1, struct2)

    def test_unify_struct_different_arity(self):
        """测试统一化不同参数个数的结构（失败）"""
        struct1 = LogicStruct("父母", ("张三", "小明"))
        struct2 = LogicStruct("父母", ("张三", "小明", "小红"))

        with pytest.raises(统一化错误):
            unify(struct1, struct2)

    def test_unify_prevents_circular_binding(self):
        """测试统一化防止循环绑定"""
        x = LogicVariable("?x")
        struct = LogicStruct("父母", (x,))

        # 尝试将x绑定到包含x的结构应该失败
        with pytest.raises(循环规则错误):
            unify(x, struct)

    def test_chained_unification(self):
        """测试链式统一化"""
        x = LogicVariable("?x")
        y = LogicVariable("?y")
        z = LogicVariable("?z")

        # x = y, y = z, z = "张三"
        subst = unify(x, y)
        subst = unify(y, z, subst)
        subst = unify(z, LogicAtom("张三"), subst)

        # 所有变量都应该绑定到"张三"
        assert subst.get_value(x).value == "张三"
        assert subst.get_value(y).value == "张三"
        assert subst.get_value(z).value == "张三"


class TestApplySubstitution:
    """测试应用替换"""

    def test_apply_to_variable(self):
        """测试应用到变量"""
        x = LogicVariable("?x")
        subst = Substitution({x.name: LogicAtom("张三")})

        result = apply_substitution(x, subst)
        assert isinstance(result, LogicAtom)
        assert result.value == "张三"

    def test_apply_to_struct(self):
        """测试应用到结构"""
        x = LogicVariable("?x")
        y = LogicVariable("?y")

        struct = LogicStruct("父母", (x, y))
        subst = Substitution({x.name: LogicAtom("张三")})

        result = apply_substitution(struct, subst)
        assert isinstance(result, LogicStruct)
        assert result.args[0].value == "张三"
        # y未绑定，应该保持为变量
        assert isinstance(result.args[1], LogicVariable)

    def test_apply_nested(self):
        """测试应用到嵌套结构"""
        x = LogicVariable("?x")
        inner = LogicStruct("关系", (x,))
        outer = LogicStruct("外层", (inner,))

        subst = Substitution({x.name: LogicAtom("张三")})
        result = apply_substitution(outer, subst)

        assert result.args[0].args[0].value == "张三"

    def test_no_substitution(self):
        """测试无替换时保持不变"""
        atom = LogicAtom("张三")
        subst = Substitution()

        result = apply_substitution(atom, subst)
        assert result == atom


class TestSubstitution:
    """测试替换类"""

    def test_empty_substitution(self):
        """测试空替换"""
        subst = Substitution()
        assert len(subst) == 0
        assert repr(subst) == "{}"

    def test_bind_variable(self):
        """测试绑定变量"""
        x = LogicVariable("?x")
        subst = Substitution()

        subst.bind(x, LogicAtom("张三"))
        assert subst.is_bound(x)
        assert subst.get_value(x).value == "张三"

    def test_mark_and_backtrack(self):
        """测试标记和回溯"""
        x = LogicVariable("?x")
        y = LogicVariable("?y")

        subst = Substitution()
        mark = subst.mark()

        # 绑定变量
        subst.bind(x, LogicAtom("张三"))
        subst.bind(y, LogicAtom("李四"))

        assert len(subst) == 2

        # 回溯
        subst.backtrack(mark)
        assert len(subst) == 0
        assert not subst.is_bound(x)
        assert not subst.is_bound(y)

    def test_copy_substitution(self):
        """测试复制替换"""
        x = LogicVariable("?x")
        subst1 = Substitution()
        subst1.bind(x, LogicAtom("张三"))

        subst2 = subst1.copy()

        assert subst2.is_bound(x)
        assert subst2.get_value(x).value == "张三"

        # 修改副本不应影响原版本
        y = LogicVariable("?y")
        subst2.bind(y, LogicAtom("李四"))
        assert not subst1.is_bound(y)


class TestKnowledgeBase:
    """测试知识库类"""

    def test_empty_knowledge_base(self):
        """测试空知识库"""
        kb = KnowledgeBase("测试")
        assert kb.name == "测试"
        assert len(kb.facts) == 0
        assert len(kb.rules) == 0

    def test_add_fact(self):
        """测试添加事实"""
        kb = KnowledgeBase("家庭")
        fact = LogicStruct("父母", ("张三", "小明"))

        kb.add_fact(fact)

        facts = kb.get_facts("父母")
        assert len(facts) == 1
        assert facts[0] == fact

    def test_add_multiple_facts(self):
        """测试添加多个事实"""
        kb = KnowledgeBase("家庭")

        kb.add_fact(LogicStruct("父母", ("张三", "小明")))
        kb.add_fact(LogicStruct("父母", ("李四", "小红")))
        kb.add_fact(LogicStruct("父母", ("王五", "乐乐")))

        facts = kb.get_facts("父母")
        assert len(facts) == 3

    def test_add_rule(self):
        """测试添加规则"""
        kb = KnowledgeBase("家庭")

        head = LogicStruct("祖父母", ("?祖", "?孙"))
        body = [LogicStruct("父母", ("?祖", "?父")), LogicStruct("父母", ("?父", "?孙"))]

        kb.add_rule(head, body)

        rules = kb.get_rules("祖父母")
        assert len(rules) == 1
        assert rules[0][0] == head
        assert rules[0][1] == body

    def test_remove_fact(self):
        """测试移除事实"""
        kb = KnowledgeBase("家庭")
        fact = LogicStruct("父母", ("张三", "小明"))

        kb.add_fact(fact)
        assert len(kb.get_facts("父母")) == 1

        result = kb.remove_fact(fact)
        assert result is True
        assert len(kb.get_facts("父母")) == 0

    def test_remove_nonexistent_fact(self):
        """测试移除不存在的事实"""
        kb = KnowledgeBase("家庭")
        fact = LogicStruct("父母", ("张三", "小明"))

        result = kb.remove_fact(fact)
        assert result is False

    def test_clear_knowledge_base(self):
        """测试清空知识库"""
        kb = KnowledgeBase("家庭")

        kb.add_fact(LogicStruct("父母", ("张三", "小明")))
        kb.add_rule(LogicStruct("祖父母", ()), [])

        assert len(kb.facts) > 0 or len(kb.rules) > 0

        kb.clear()
        assert len(kb.facts) == 0
        assert len(kb.rules) == 0

    def test_knowledge_base_repr(self):
        """测试知识库字符串表示"""
        kb = KnowledgeBase("家庭")
        kb.add_fact(LogicStruct("父母", ("张三", "小明")))

        repr_str = repr(kb)
        assert "家庭" in repr_str
        assert "事实" in repr_str


class TestNormalizeTerm:
    """测试项标准化"""

    def test_normalize_string_to_atom(self):
        """测试将字符串转换为原子"""
        result = normalize_term("张三")
        assert isinstance(result, LogicAtom)
        assert result.value == "张三"

    def test_normalize_question_mark_to_variable(self):
        """测试将问号字符串转换为变量"""
        result = normalize_term("?x")
        assert isinstance(result, LogicVariable)
        assert result.name == "?x"

    def test_normalize_dict_to_struct(self):
        """测试将字典转换为结构"""
        data = {"predicate": "父母", "args": ["张三", "小明"]}
        result = normalize_term(data)

        assert isinstance(result, LogicStruct)
        assert result.predicate == "父母"
        assert result.args[0].value == "张三"
        assert result.args[1].value == "小明"

    def test_normalize_already_logic_term(self):
        """测试已经是逻辑项的情况"""
        var = LogicVariable("?x")
        result = normalize_term(var)

        assert result is var


class TestIsUnifiable:
    """测试是否可统一化检查"""

    def test_is_unifiable_true(self):
        """测试可统一化（真）"""
        x = LogicVariable("?x")
        assert is_unifiable(x, LogicAtom("张三"))
        assert is_unifiable(LogicAtom("张三"), LogicAtom("张三"))

    def test_is_unifiable_false(self):
        """测试不可统一化（假）"""
        assert not is_unifiable(LogicAtom("张三"), LogicAtom("李四"))
        assert not is_unifiable(
            LogicStruct("父母", ()),
            LogicStruct("子女", ())
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
