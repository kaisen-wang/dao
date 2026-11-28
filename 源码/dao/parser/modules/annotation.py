"""@ 注解解析混入"""

from ...ast_nodes import Annotation
from ...errors import 语法错误
from ...tokens import TokenType


class AnnotationParser:
    """注解（@装饰器）解析方法集"""

    def parse_annotations(self) -> list[Annotation]:
        """解析一个或多个连续书写的注解（每个注解独占一行）。

        调用前当前 token 必须是 ``TokenType.注解``。返回的注解按书写顺序
        排列；注解本身的参数支持位置参数与 ``名称 = 表达式`` 两种形式。
        """
        annotations: list[Annotation] = []

        while self.current.type == TokenType.注解:
            token = self.current
            name = token.value
            self.advance()  # 消费 @名称 token

            args = []
            kwargs = {}
            if self.current.type == TokenType.左括号:
                self.advance()  # 消费 (
                while self.current.type != TokenType.右括号:
                    if (
                        self.current.type == TokenType.标识符
                        and self.peek().type == TokenType.赋值
                    ):
                        key = self.advance().value
                        self.advance()  # 消费 =
                        kwargs[key] = self.parse_expression()
                    else:
                        args.append(self.parse_expression())
                    if not self.match(TokenType.逗号):
                        break
                self.expect(TokenType.右括号, "注解参数需要 ')'")

            annotations.append(
                Annotation(
                    name=name,
                    args=args,
                    kwargs=kwargs,
                    line=token.line,
                    column=token.column,
                )
            )

            # 同一行不允许出现两个注解
            if self.current.type == TokenType.注解:
                raise 语法错误(
                    "注解之间必须用换行分隔，同一行只能写一个注解",
                    self.current.line,
                    self.current.column,
                    self.source,
                )

            # 注解之间以换行分隔；同时消费掉注解行末尾的换行，
            # 使调用方直接面对被注解的声明。
            self.skip_newlines()

        return annotations
