"""模块系统解析混入"""

from ...tokens import TokenType
from ...ast_nodes import ImportStmt, ExportStmt


class ModuleSystemParser:
    """模块系统解析方法集"""

    def parse_export_stmt(self) -> ExportStmt:
        """解析导出语句：导出 名称1, 名称2, ..."""
        token = self.advance()  # 消费 导出

        names = []

        name_token = self.expect(TokenType.标识符, "导出语句需要名称")
        names.append(name_token.value)

        while self.match(TokenType.逗号):
            name_token = self.expect(TokenType.标识符, "期望导出的名称")
            names.append(name_token.value)

        self.match(TokenType.换行)
        return ExportStmt(
            names=names,
            line=token.line,
            column=token.column,
        )


    def parse_import_stmt(self, is_from_import: bool = False) -> ImportStmt:
        """解析导入语句：导入 模块 / 从 模块 导入 {项}"""

        if is_from_import:
            # 已经在 parse_statement 中消费了 "从"
            token = self.current  # 当前 token 是模块名
            module_token = self.expect(TokenType.标识符, "导入需要模块名")
            module_path = module_token.value

            # 点分路径：工具.数学
            while self.match(TokenType.点):
                next_name = self.expect(TokenType.标识符, "模块路径需要名称")
                module_path += "." + next_name.value

            self.expect(TokenType.导入, "期望 '导入' 关键字")

            names = []
            name_token = self.expect(TokenType.标识符, "导入语句需要名称")
            alias = None
            if self.match(TokenType.作为):
                alias_token = self.expect(TokenType.标识符, "'作为' 后需要别名")
                alias = alias_token.value
            names.append((name_token.value, alias))

            while self.match(TokenType.逗号):
                name_token = self.expect(TokenType.标识符, "期望导入的名称")
                alias = None
                if self.match(TokenType.作为):
                    alias_token = self.expect(TokenType.标识符, "'作为' 后需要别名")
                    alias = alias_token.value
                names.append((name_token.value, alias))

            self.match(TokenType.换行)
            return ImportStmt(
                module_path=module_path,
                names=names,
                alias=None,
                is_from_import=True,
                line=token.line,
                column=token.column,
            )
        else:
            # 普通 "导入 模块" 语法
            token = self.advance()  # 消费 导入
            module_token = self.expect(TokenType.标识符, "导入需要模块名")
            module_path = module_token.value

            # 点分路径：工具.数学
            while self.match(TokenType.点):
                next_name = self.expect(TokenType.标识符, "模块路径需要名称")
                module_path += "." + next_name.value

            alias = None
            if self.match(TokenType.作为):
                alias_token = self.expect(TokenType.标识符, "'作为' 后需要别名")
                alias = alias_token.value

            self.match(TokenType.换行)
            return ImportStmt(
                module_path=module_path,
                names=[],
                alias=alias,
                is_from_import=False,
                line=token.line,
                column=token.column,
            )

    # 赋值与表达式语句

