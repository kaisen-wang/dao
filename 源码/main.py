#!/usr/bin/env python3
"""
道（Dao）编程语言 - 主入口
=========================

提供三种运行模式：
1. REPL模式：交互式命令行（无参数启动）
2. 文件模式：执行 .道 文件（传入文件路径）
3. 项目模式：读取项目根目录的 道.配置，按「入口」字段运行项目

另提供依赖包与应用打包子命令：pack / 打包、install / 安装、packages / 包列表、build / 构建应用、run / 运行（运行项目或 .道应用 应用包）。

使用方法：
    python main.py                      # 启动 REPL
    python main.py 你好世界.道          # 执行文件
    python main.py run                  # 运行当前项目（读取 道.配置）
    python main.py 运行                 # 同上（中文命令）
    python main.py run 路径/到/项目     # 运行指定目录下的项目
    python main.py run 应用.道应用      # 解压并运行 .道应用 应用包
    python main.py pack                 # 把当前项目打成 .道包
    python main.py install 包.道包      # 把 .道包 安装到当前项目
    python main.py build               # 把当前项目打成 .道应用
"""

import argparse
import os
import shutil
import sys
import tempfile

# 确保能导入 dao 包
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dao.errors import 道错误
from dao.interpreter import Interpreter
from dao.lexer import Lexer
from dao.package.config import resolve_entry_path
from dao.parser import Parser
from dao.version import banner_text, version_text


def run_source(source: str, interpreter: Interpreter, filename: str = "<输入>",
               mode: str = "interpreter", type_check: bool = False, disasm: bool = False,
               jit: bool = False, type_check_warn: bool = False) -> object:
    lexer = Lexer(source, filename)
    tokens = lexer.tokenize()
    parser = Parser(tokens, source)
    ast = parser.parse()

    if type_check or type_check_warn:
        from dao.types.checker import TypeInferenceEngine
        base_dir = os.getcwd() if filename == "<输入>" else os.path.dirname(os.path.abspath(filename))
        engine = TypeInferenceEngine(base_dir=base_dir)
        reports = engine.check(ast)
        if reports and type_check:
            # 阻断模式：输出中文诊断并以非 0 退出码停止执行。
            for r in reports:
                print(f"类型错误: {r.message} (行{r.line}, 列{r.column})", file=sys.stderr)
            sys.exit(1)
        if reports and type_check_warn:
            # 仅警告模式：保留旧行为，打印警告后继续执行。
            for r in reports:
                print(f"类型警告: {r.message} (行{r.line}, 列{r.column})")

    if mode == "vm":
        from dao.bytecode.compiler import BytecodeCompiler
        from dao.bytecode.disassembler import Disassembler
        from dao.vm.core import VirtualMachine
        compiler = BytecodeCompiler()
        code = compiler.compile(ast)
        if disasm:
            disassembler = Disassembler()
            print(disassembler.disassemble(code))
        vm = VirtualMachine()
        if jit:
            vm.enable_jit()
        return vm.run(code)

    result = interpreter.execute(ast, source=source)
    return result


def run_file(filepath: str, mode: str = "interpreter", type_check: bool = False,
             disasm: bool = False, jit: bool = False, type_check_warn: bool = False):
    """执行一个 .道 文件"""
    if not os.path.exists(filepath):
        print(f"错误：文件 '{filepath}' 不存在")
        sys.exit(1)

    with open(filepath, 'r', encoding='utf-8') as f:
        source = f.read()

    interpreter = Interpreter()

    try:
        run_source(source, interpreter, filepath, mode=mode, type_check=type_check,
                   disasm=disasm, jit=jit, type_check_warn=type_check_warn)
    except 道错误 as e:
        if not e.filename:
            e.filename = filepath
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n程序被中断")
        sys.exit(130)


# ---------------------------------------------------------------------------
# 项目模式：dao run / 道 运行
# ---------------------------------------------------------------------------

CONFIG_FILENAME = "道.配置"
RUN_COMMANDS = ("run", "运行")
PACK_COMMANDS = ("pack", "打包")
INSTALL_COMMANDS = ("install", "安装")
LIST_COMMANDS = ("packages", "包列表")
BUILD_COMMANDS = ("build", "构建应用", "打包应用")
PUBLISH_COMMANDS = ("publish", "发布")
LOCK_COMMANDS = ("lock", "更新锁")
REPO_COMMANDS = ("repo", "仓库查询")


# 入口路径解析与包管理器共用 dao.package.config.resolve_entry_path，
# 这里通过导入保持 main.resolve_entry_path 的既有调用方式。


def run_project(project_path: str | None = None, mode: str = "interpreter",
                type_check: bool = False, disasm: bool = False, jit: bool = False,
                type_check_warn: bool = False):
    """读取 ``道.配置`` 并运行项目入口。

    :param project_path: 项目目录，默认当前工作目录
    :raises SystemExit: 配置缺失、入口缺失或入口文件不存在时退出并报错
    """
    from dao.package.config import PackageConfig

    project_dir = os.path.abspath(project_path or os.getcwd())
    if not os.path.isdir(project_dir):
        print(f"错误：项目目录不存在：{project_dir}", file=sys.stderr)
        sys.exit(1)

    config_path = os.path.join(project_dir, CONFIG_FILENAME)
    if not os.path.isfile(config_path):
        print(f"错误：项目目录下找不到 {CONFIG_FILENAME}：{project_dir}", file=sys.stderr)
        sys.exit(1)

    try:
        config = PackageConfig.from_file(config_path)
    except (OSError, UnicodeError, ValueError) as e:
        print(f"错误：无法读取 {CONFIG_FILENAME}：{e}", file=sys.stderr)
        sys.exit(1)

    entry = (config.entry or "").strip()
    if not entry:
        print(f"错误：{CONFIG_FILENAME} 中未配置「入口」", file=sys.stderr)
        sys.exit(1)

    try:
        entry_path = resolve_entry_path(project_dir, entry)
    except ValueError as e:
        print(f"错误：{e}", file=sys.stderr)
        sys.exit(1)

    if not os.path.isfile(entry_path):
        print(f"错误：入口文件不存在：{entry_path}", file=sys.stderr)
        sys.exit(1)

    # 模块导入基于 cwd 解析，切到项目根目录后再执行入口
    os.chdir(project_dir)
    run_file(entry_path, mode=mode, type_check=type_check, disasm=disasm, jit=jit,
             type_check_warn=type_check_warn)


def _handle_macro_debug_command(line: str, interpreter: Interpreter):
    """处理宏调试 REPL 命令

    支持的命令：
    - :宏列表 — 列出所有已注册的宏
    - :宏追踪 — 开启/关闭宏展开追踪
    - :宏追踪状态 — 查看追踪状态
    - :宏调用栈 — 显示当前宏展开调用栈
    - :宏帮助 — 显示宏调试帮助
    """

    cmd = line.strip()

    if cmd == ':宏列表':
        registry = interpreter.macro_registry
        macros = registry.get_all_macros()
        if not macros:
            print("当前无已注册的宏")
        else:
            print(f"已注册 {len(macros)} 个宏：")
            for m in macros:
                macro_type = "模式匹配" if m.is_pattern_macro else "普通"
                params = ", ".join(m.parameters)
                print(f"  !{m.name}({params}) [{macro_type}]")
        return True

    if cmd == ':宏追踪':
        # 切换追踪状态
        # 通过 interpreter 的内部状态控制追踪
        if not hasattr(interpreter, '_macro_trace'):
            interpreter._macro_trace = False
        interpreter._macro_trace = not interpreter._macro_trace
        state = "开启" if interpreter._macro_trace else "关闭"
        print(f"宏展开追踪已{state}")
        return True

    if cmd == ':宏追踪状态':
        state = "开启" if getattr(interpreter, '_macro_trace', False) else "关闭"
        print(f"宏展开追踪状态: {state}")
        return True

    if cmd == ':宏调用栈':
        # 调用栈在展开过程中才有内容，这里显示上一次展开的调用栈
        if hasattr(interpreter, '_last_macro_call_stack'):
            stack = interpreter._last_macro_call_stack
            if not stack:
                print("宏调用栈为空（无正在进行的宏展开）")
            else:
                print("宏展开调用栈:")
                for i, entry in enumerate(stack):
                    indent = "  " * i
                    name = entry.get("name", "?")
                    line = entry.get("line", 0)
                    depth = entry.get("depth", 0)
                    print(f"{indent}[{i}] !{name} (行 {line}, 深度 {depth})")
        else:
            print("宏调用栈为空（尚未执行过宏展开）")
        return True

    if cmd == ':宏帮助':
        print("宏调试命令：")
        print("  :宏列表       — 列出所有已注册的宏")
        print("  :宏追踪       — 开启/关闭宏展开追踪")
        print("  :宏追踪状态   — 查看追踪状态")
        print("  :宏调用栈     — 显示当前宏展开调用栈")
        print("  :宏帮助       — 显示此帮助信息")
        return True

    # 不是宏调试命令
    return False


# ---------------------------------------------------------------------------
# REPL 输入与多行判定辅助
# ---------------------------------------------------------------------------

# 出现在行首即可判定为「块开始」的关键字（后跟空白或行尾才算独立关键字）
_BLOCK_KEYWORDS = (
    '函数', '异步函数', '如果', '否则如果', '否则', '当', '遍历',
    '尝试', '捕获', '最终', '类型',
)

_prompt_session = None
_prompt_session_tried = False


def _get_prompt_session():
    """惰性创建 prompt_toolkit 的 PromptSession；导入失败返回 None。"""
    global _prompt_session, _prompt_session_tried
    if not _prompt_session_tried:
        _prompt_session_tried = True
        try:
            from prompt_toolkit import PromptSession
            _prompt_session = PromptSession()
        except Exception:  # noqa: BLE001 - 可选依赖缺失或环境不兼容时静默降级
            _prompt_session = None
    return _prompt_session


def _read_line(prompt: str) -> str:
    """读取一行输入。

    交互终端下优先使用 prompt_toolkit（提供历史与行编辑能力），
    非交互终端（如管道）或依赖缺失时优雅降级到内置 input()。
    """
    if sys.stdin.isatty():
        session = _get_prompt_session()
        if session is not None:
            return session.prompt(prompt)
    return input(prompt)


def _find_top_level_colon(line: str) -> tuple[int, bool]:
    """查找行内最后一个位于顶层（括号外、字符串外）的冒号。

    返回 ``(冒号位置, 冒号后是否还有非空代码)``；未找到返回 ``(-1, False)``。
    这样可避免把字符串、字典字面量里的冒号误判为块起始符。
    """
    depth = 0
    quote = None
    escaped = False
    last_colon = -1
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if escaped:
            escaped = False
            i += 1
            continue
        if quote:
            if ch == '\\':
                escaped = True
            elif ch == quote:
                # 三引号字符串：\"\"\" 或 '''
                if (quote in ('"', "'") and i + 2 < n
                        and line[i + 1] == quote and line[i + 2] == quote):
                    i += 3
                    quote = None
                    continue
                quote = None
            i += 1
            continue
        if ch in ('"', "'", '`'):
            if (ch in ('"', "'") and i + 2 < n
                    and line[i + 1] == ch and line[i + 2] == ch):
                quote = ch
                i += 3
                continue
            quote = ch
        elif ch in '([{':
            depth += 1
        elif ch in ')]}':
            depth = max(0, depth - 1)
        elif ch in (':', '：') and depth == 0:
            last_colon = i
        i += 1

    has_code_after = last_colon >= 0 and bool(line[last_colon + 1:].strip())
    return last_colon, has_code_after


def _leading_block_keyword(line: str) -> str | None:
    """若行首是一个独立的块关键字，返回该关键字，否则返回 None。"""
    code = line.lstrip()
    for kw in _BLOCK_KEYWORDS:
        if code.startswith(kw):
            rest = code[len(kw):]
            if rest == '' or rest[0].isspace():
                return kw
    return None


def _needs_continuation(line: str) -> bool:
    """判断单行输入是否尚未写完，需要进入续行模式。

    判定规则（按优先级）：
    1. 空行与注释不触发续行；
    2. 顶层冒号后还有代码（如 ``如果 x: 语句``）视为单行语句；
    3. 顶层冒号结尾（如 ``如果 x:``）触发续行；
    4. 行首为块关键字（如 ``如果 x > 0``）触发续行。
    字符串与字典字面量内部的冒号不会被误判。
    """
    if not line.strip():
        return False
    stripped = line.lstrip()
    if stripped.startswith(('//', '注：', '注:')):
        return False

    colon_pos, has_code_after = _find_top_level_colon(line)
    if has_code_after:
        return False
    if colon_pos >= 0:
        return True
    return _leading_block_keyword(line) is not None


def _print_help():
    """打印 REPL 可用命令帮助。"""
    print("REPL 命令：")
    print("  :帮助             — 显示本帮助信息")
    print("  :粘贴 / :多行      — 进入多行粘贴模式，输入 '.' 或 ':结束' 完成，':取消' 放弃")
    print("  :宏列表           — 列出所有已注册的宏")
    print("  :宏追踪           — 开启/关闭宏展开追踪")
    print("  :宏追踪状态       — 查看宏展开追踪状态")
    print("  :宏调用栈         — 显示当前宏展开调用栈")
    print("  :宏帮助           — 显示宏调试帮助")
    print("  退出 / exit / quit — 退出 REPL")
    print("提示：输入块关键字（如 '如果 x > 0'）会自动进入续行，空行结束。")


def _read_paste_mode():
    """读取多行粘贴模式的内容。

    返回拼接后的源码字符串；用户取消或没有任何内容时返回 None。
    """
    print("已进入多行粘贴模式：输入 '.' 或 ':结束' 完成，':取消' 放弃。")
    lines = []
    while True:
        try:
            line = _read_line("...   ")
        except (EOFError, KeyboardInterrupt):
            break
        stripped = line.strip()
        if stripped in ('.', ':结束', ':完成'):
            break
        if stripped == ':取消':
            print("已取消多行输入")
            return None
        lines.append(line)
    if not lines:
        return None
    return '\n'.join(lines)


def _execute_repl_source(source: str, interpreter: Interpreter):
    """执行一段 REPL 源码并按既有规则显示结果。"""
    result = run_source(source + '\n', interpreter)
    if result is not None:
        if isinstance(result, bool):
            print("真" if result else "假")
        else:
            print(result)


def run_repl():
    """启动交互式命令行（REPL）"""
    print("═" * 50)
    print(banner_text())
    print("  交互式命令行 - 输入代码按回车执行")
    print("  输入 ':帮助' 查看所有命令")
    print("  输入 '退出' 或按 Ctrl+C 退出")
    print("═" * 50)
    print()

    interpreter = Interpreter()

    while True:
        try:
            line = _read_line("道 > ")
            cmd = line.strip()

            if cmd in ('退出', 'exit', 'quit'):
                print("再见！")
                break

            if not cmd:
                continue

            # REPL 通用命令
            if cmd == ':帮助':
                _print_help()
                continue

            if cmd in (':粘贴', ':多行'):
                source = _read_paste_mode()
                if source is not None:
                    _execute_repl_source(source, interpreter)
                continue

            # 宏调试命令（保留原有 :宏 系列行为）
            if cmd.startswith(':宏'):
                if _handle_macro_debug_command(line, interpreter):
                    continue
                print(f"未知命令：{cmd}（输入 ':帮助' 查看可用命令）")
                continue

            if cmd.startswith(':'):
                print(f"未知命令：{cmd}（输入 ':帮助' 查看可用命令）")
                continue

            # 多行输入：块关键字或顶层冒号结尾进入续行，空行结束
            source = line
            if _needs_continuation(line):
                while True:
                    try:
                        continuation = _read_line("...   ")
                    except EOFError:
                        break
                    if continuation.strip() == '':
                        break
                    source += '\n' + continuation

            _execute_repl_source(source, interpreter)

        except 道错误 as e:
            print(f"❌ {e}")
        except KeyboardInterrupt:
            print("\n再见！")
            break
        except EOFError:
            print("\n再见！")
            break


def _add_execution_args(arg_parser: argparse.ArgumentParser):
    """给解析器添加通用的执行选项。"""
    arg_parser.add_argument("--mode", choices=["interpreter", "vm"], default="interpreter",
                            help="执行模式：interpreter（默认）或 vm")
    arg_parser.add_argument("--type-check", action="store_true",
                            help="启用阻断式类型检查（发现类型错误时输出诊断并以非 0 退出码停止执行）")
    arg_parser.add_argument("--type-check-warn", action="store_true",
                            help="只输出类型警告、不阻断执行（兼容旧行为）")
    arg_parser.add_argument("--disasm", action="store_true", help="输出字节码反汇编结果（仅 VM 模式）")
    arg_parser.add_argument("--jit", action="store_true", help="启用 JIT 编译（仅 VM 模式）")


def _run_app(archive: str, mode: str = "interpreter", type_check: bool = False,
             disasm: bool = False, jit: bool = False, type_check_warn: bool = False):
    """解压并运行一个 ``.道应用``（由 ``run`` 命令在参数为应用包时调用）。"""
    from dao.package.app import check_app_dao_version, extract_app, inspect_app

    try:
        manifest = inspect_app(archive)
        check_app_dao_version(manifest)
        temp_dir = tempfile.mkdtemp(prefix="dao-app-")
    except (OSError, ValueError) as e:
        print(f"错误：运行应用失败：{e}", file=sys.stderr)
        sys.exit(1)

    original_cwd = os.getcwd()
    try:
        app_dir = extract_app(archive, temp_dir)
        os.chdir(app_dir)
        run_project(app_dir, mode=mode, type_check=type_check,
                    disasm=disasm, jit=jit, type_check_warn=type_check_warn)
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(temp_dir, ignore_errors=True)


def _main_run(argv: list[str], command: str = "run"):
    """解析 ``run`` / ``运行`` 子命令的参数。

    ``.道应用`` 文件按应用包运行，其余按项目目录运行（默认当前目录）。
    """
    arg_parser = argparse.ArgumentParser(
        prog=f"dao {command}",
        description="运行项目或 .道应用 应用包（读取 道.配置，按「入口」字段运行）",
    )
    arg_parser.add_argument("path", nargs="?", default=".",
                            help="项目目录或 .道应用 应用包（默认当前目录）")
    _add_execution_args(arg_parser)
    args = arg_parser.parse_args(argv)

    from dao.package.app import APP_SUFFIX

    if args.path.endswith(APP_SUFFIX):
        _run_app(args.path, mode=args.mode, type_check=args.type_check,
                 disasm=args.disasm, jit=args.jit,
                 type_check_warn=args.type_check_warn)
        return

    run_project(args.path, mode=args.mode, type_check=args.type_check,
                disasm=args.disasm, jit=args.jit,
                type_check_warn=args.type_check_warn)


def _main_pack(argv: list[str], command: str = "pack"):
    """把项目打成 ``.道包`` 依赖包。"""
    arg_parser = argparse.ArgumentParser(
        prog=f"dao {command}",
        description="把道语言项目打成 .道包 依赖包（需 道.配置）",
    )
    arg_parser.add_argument("path", nargs="?", default=".",
                            help="项目目录（默认当前目录）")
    arg_parser.add_argument("-o", "--output",
                            help="输出文件路径或目录（默认写到项目根目录）")
    args = arg_parser.parse_args(argv)

    from dao.package.packer import pack_project

    try:
        archive_path = pack_project(args.path, args.output)
    except (OSError, ValueError) as e:
        print(f"错误：打包失败：{e}", file=sys.stderr)
        sys.exit(1)

    print(f"已生成依赖包：{archive_path}")


def _main_install(argv: list[str], command: str = "install"):
    """安装 ``.道包`` 依赖包。"""
    arg_parser = argparse.ArgumentParser(
        prog=f"dao {command}",
        description="安装 .道包 到项目的 道包/ 目录（或全局目录）",
    )
    arg_parser.add_argument("archive", nargs="?", help="要安装的 .道包 文件")
    arg_parser.add_argument("-p", "--project", default=".",
                            help="目标项目目录（默认当前目录）")
    arg_parser.add_argument("-g", "--global", dest="global_install", action="store_true",
                            help="安装到 ~/.道/包/ 全局目录")
    arg_parser.add_argument("-f", "--force", action="store_true",
                            help="已安装不同版本时强制覆盖")
    arg_parser.add_argument("--skip-version-check", action="store_true",
                            help="跳过包声明的「道版本」兼容性检查")
    arg_parser.add_argument("--update-lock", action="store_true",
                            help="按最新约束更新锁文件（显式安装默认已记录精确版本）")
    arg_parser.add_argument("--from-lock", metavar="包名",
                            help="按 道.锁 记录的精确版本安装指定包")
    args = arg_parser.parse_args(argv)

    if not args.archive and not args.from_lock:
        arg_parser.error("请提供 .道包 文件，或使用 --from-lock 指定包名")

    from dao.package.manager import PackageManager

    try:
        manager = PackageManager(project_dir=args.project)
        if args.from_lock:
            target = manager.install(
                name=args.from_lock,
                use_lock=True,
                global_install=args.global_install,
                force=args.force,
                check_version=not args.skip_version_check,
            )
        else:
            # 显式指定包路径时不做锁漂移校验（用户已明确版本）；
            # 仅 --update-lock 时把该版本写入锁文件。
            target = manager.install(
                args.archive,
                global_install=args.global_install,
                force=args.force,
                check_version=not args.skip_version_check,
                use_lock=False,
                update_lock=args.update_lock,
            )
    except (OSError, ValueError) as e:
        print(f"错误：安装失败：{e}", file=sys.stderr)
        sys.exit(1)

    print(f"已安装依赖：{target}")


def _main_list_packages(argv: list[str], command: str = "包列表"):
    """列出已安装的依赖包。"""
    arg_parser = argparse.ArgumentParser(
        prog=f"dao {command}",
        description="列出已安装的道语言依赖包",
    )
    arg_parser.add_argument("path", nargs="?", default=".",
                            help="项目目录（默认当前目录）")
    arg_parser.add_argument("-g", "--global", dest="global_install", action="store_true",
                            help="列出 ~/.道/包/ 全局目录")
    args = arg_parser.parse_args(argv)

    from dao.package.packer import list_installed_packages

    packages = list_installed_packages(args.path, args.global_install)
    if not packages:
        print("尚未安装任何依赖包")
    else:
        print("已安装依赖：")
        for name, version, dao_version in packages:
            suffix = f"（道版本 {dao_version}）" if dao_version else ""
            print(f"  {name} {version}{suffix}")


def _main_build_app(argv: list[str], command: str = "build"):
    """把项目打成 ``.道应用`` 可运行应用包。"""
    arg_parser = argparse.ArgumentParser(
        prog=f"dao {command}",
        description="把道语言项目打成 .道应用（含已安装依赖，可直接运行）",
    )
    arg_parser.add_argument("path", nargs="?", default=".",
                            help="项目目录（默认当前目录）")
    arg_parser.add_argument("-o", "--output",
                            help="输出文件路径或目录（默认写到项目根目录）")
    arg_parser.add_argument("--no-deps", action="store_true",
                            help="不把 道包/ 下已安装的依赖打进应用包")
    args = arg_parser.parse_args(argv)

    from dao.package.app import build_app

    try:
        archive_path = build_app(args.path, args.output, include_deps=not args.no_deps)
    except (OSError, ValueError) as e:
        print(f"错误：打包应用失败：{e}", file=sys.stderr)
        sys.exit(1)

    print(f"已生成应用包：{archive_path}")


def _main_default(argv: list[str]):
    """原有的 REPL / 单文件执行模式。"""
    arg_parser = argparse.ArgumentParser(description="道（Dao）编程语言")
    arg_parser.add_argument("-V", "--version", action="version", version=version_text(),
                            help="显示版本号信息并退出")
    arg_parser.add_argument("file", nargs="?", help="要执行的 .道 文件")
    _add_execution_args(arg_parser)
    args = arg_parser.parse_args(argv)

    if args.file:
        run_file(args.file, mode=args.mode, type_check=args.type_check, disasm=args.disasm,
                 jit=args.jit, type_check_warn=args.type_check_warn)
    else:
        run_repl()


def _main_publish(argv: list[str], command: str = "publish"):
    """把项目打成 .道包 并写入本地仓库索引。"""
    arg_parser = argparse.ArgumentParser(
        prog=f"dao {command}",
        description="发布依赖包到本地仓库（需 道.配置）",
    )
    arg_parser.add_argument("path", nargs="?", default=".",
                            help="项目目录（默认当前目录）")
    arg_parser.add_argument("-o", "--output",
                            help="输出文件路径或目录（默认写到项目根目录）")
    arg_parser.add_argument("--skip-version-check", action="store_true",
                            help="跳过包声明的「道版本」兼容性检查")
    args = arg_parser.parse_args(argv)

    from dao.package.publish import publish

    try:
        result = publish(args.path, args.output,
                         check_version=not args.skip_version_check)
    except (OSError, ValueError) as e:
        print(f"错误：发布失败：{e}", file=sys.stderr)
        sys.exit(1)

    print(f"已发布依赖包：{result.archive_path}")
    print(f"已写入本地仓库：{result.entry.path}")


def _main_lock(argv: list[str], command: str = "lock"):
    """根据项目依赖约束更新锁文件。"""
    arg_parser = argparse.ArgumentParser(
        prog=f"dao {command}",
        description="根据 道.配置 的依赖约束更新 道.锁",
    )
    arg_parser.add_argument("-p", "--project", default=".",
                            help="项目目录（默认当前目录）")
    args = arg_parser.parse_args(argv)

    from dao.package.manager import PackageManager

    try:
        lock = PackageManager(project_dir=args.project).update_lock()
    except (OSError, ValueError) as e:
        print(f"错误：更新锁文件失败：{e}", file=sys.stderr)
        sys.exit(1)

    print(f"已更新锁文件：{lock.path}")


def _main_repo(argv: list[str], command: str = "repo"):
    """查询本地仓库索引中的包。"""
    arg_parser = argparse.ArgumentParser(
        prog=f"dao {command}",
        description="查询 ~/.道/仓库/ 本地包索引",
    )
    arg_parser.add_argument("name", nargs="?", help="包名（省略则列出全部）")
    arg_parser.add_argument("--constraint", help="版本约束（如 ^1.2.0）")
    arg_parser.add_argument("--sync", action="store_true",
                            help="先把已安装包同步进索引再查询")
    args = arg_parser.parse_args(argv)

    from dao.package.repository import RepositoryIndex

    try:
        repo = RepositoryIndex()
        if args.sync:
            repo.sync_installed()
        entries = repo.query(args.name, args.constraint)
    except (OSError, ValueError) as e:
        print(f"错误：查询仓库失败：{e}", file=sys.stderr)
        sys.exit(1)

    if not entries:
        print("仓库中没有匹配的包")
    else:
        for entry in entries:
            print(f"{entry.name} {entry.version} ← {entry.path}")


def main():
    """主函数"""
    argv = sys.argv[1:]
    if argv and argv[0] in RUN_COMMANDS:
        _main_run(argv[1:], argv[0])
    elif argv and argv[0] in PACK_COMMANDS:
        _main_pack(argv[1:], argv[0])
    elif argv and argv[0] in INSTALL_COMMANDS:
        _main_install(argv[1:], argv[0])
    elif argv and argv[0] in LIST_COMMANDS:
        _main_list_packages(argv[1:], argv[0])
    elif argv and argv[0] in BUILD_COMMANDS:
        _main_build_app(argv[1:], argv[0])
    elif argv and argv[0] in PUBLISH_COMMANDS:
        _main_publish(argv[1:], argv[0])
    elif argv and argv[0] in LOCK_COMMANDS:
        _main_lock(argv[1:], argv[0])
    elif argv and argv[0] in REPO_COMMANDS:
        _main_repo(argv[1:], argv[0])
    else:
        _main_default(argv)


if __name__ == "__main__":
    main()
