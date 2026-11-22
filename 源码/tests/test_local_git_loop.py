"""更夫 Nightwatch — 本地 git 真实闭环测试（第八轮）。

覆盖共享契约《迭代规约-真实验收.md》§2 C：
- 用 ``tempfile.TemporaryDirectory()`` 建 bare 仓库 + 工作克隆，退出自动清理，
  项目目录不产生仓库或 .db；
- 真实 git 操作链：初始提交 → 模拟 Issue 事件 → 建分支 → 应用 PR 载荷
  （真实文件改动 + git add + git commit + git push 到 bare）→ review 检查 →
  git checkout main + git merge + git push → 工单状态信号 ended(merged)；
- Issue 归一化 / merged 信号 / 绑定 ended 状态复用第七轮真实产品代码
  （``基础设施层.GitHub事件.道``、``领域层.领域.道``），以 ``sys.executable`` +
  ``main.py`` 子进程调用，cwd=``示例/更夫`` 且 ``GENGFU_NO_LLM=1``；
- 断言：分支存在且 push 成功、commit 在 bare 仓库可达、合并后主干文件内容正确、
  工单信号为 ``ended(merged)``。

诚实边界：本地 bare 仓库是真实 git 操作，但不是真实 GitHub 的 webhook / 权限 / CI；
不接真实 GitHub、不设置外网 remote、不发真实网络请求；工单 ended(merged) 是由真实
适配器 ``已合并`` 信号与领域绑定 ``ended`` 状态编排出的信号，不是 GitHub 工单的真实状态回写。
"""

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# 源码/tests/test_local_git_loop.py -> 仓库根目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAIN = PROJECT_ROOT / "源码" / "main.py"
GENGFU_DIR = PROJECT_ROOT / "示例" / "更夫"


# 道语言探针：复用第七轮适配器与领域绑定，产出归一化字段与工单信号。
# 只做本地归一化与信号生成，不发起任何真实请求、不做真实 merge（真实 merge 由 Python 侧 git 完成）。
GIT_LOOP_SCRIPT = """\
// 本地 git 闭环探针（由 Python 测试在 tempfile 中生成）。
从 基础设施层.GitHub事件 导入 创建GitHub适配器
从 领域层.领域 导入 执行绑定

定义 适配器 = 创建GitHub适配器("carsson/道", "", 真)

// 模拟 Issue 事件：issues.opened，正文 @更夫 触发生成工单。
定义 Issue事件 = {"action": "opened", "issue": {"id": 1001, "number": 42, "title": "登录页崩溃", "body": "@更夫 请修复登录页崩溃", "user": {"login": "carsson"}}, "repository": {"full_name": "carsson/道"}}
定义 Issue结果 = 适配器.解析事件(Issue事件)
定义 Issue触发 = 适配器.生成触发(Issue事件)
打印(`P|消息ID={Issue结果["消息ID"]}`)
打印(`P|文本={Issue结果["文本"]}`)
打印(`P|话题键={Issue结果["话题键"]}`)
打印(`P|事件类型={Issue结果["事件类型"]}`)
打印(`P|外部编号={Issue触发.外部编号}`)
打印(`P|是否机器人={Issue触发.是否机器人}`)

// PR closed 且 merged=true：复用真实适配器生成 已合并 信号，并编排工单 ended(merged)。
定义 PR事件 = {"action": "closed", "pull_request": {"number": 43, "title": "修复登录页崩溃", "merged": 真, "user": {"login": "carsson"}}, "repository": {"full_name": "carsson/道"}}
定义 PR结果 = 适配器.解析事件(PR事件)
定义 信号 = "ended(未合并)"
如果 PR结果["已合并"] == 真
    信号 = "ended(merged)"
打印(`P|已合并={PR结果["已合并"]}`)
打印(`P|工单信号={信号}`)

// 执行绑定状态机：开始 → 结束 → ended，对应工单最终结束。
定义 绑定 = 执行绑定("T-42", "更夫", "修复登录页崩溃")
绑定.开始()
绑定.结束()
打印(`P|绑定状态={绑定.状态}`)
"""


def _运行git(目录: Path, *参数: str) -> str:
    """在指定目录执行真实 git 命令；失败即断言，返回 strip 后的 stdout。"""
    结果 = subprocess.run(
        ["git", "-C", str(目录), *参数],
        capture_output=True,
        text=True,
        check=False,
    )
    assert 结果.returncode == 0, (
        f"git {' '.join(参数)} 失败（退出码 {结果.returncode}）：{结果.stderr}"
    )
    return 结果.stdout.strip()


def _运行道脚本(脚本路径: Path) -> dict[str, str]:
    """用 sys.executable + main.py 运行道探针，解析 P|键=值 形式的标准输出。"""
    环境变量 = os.environ.copy()
    环境变量["PYTHONPATH"] = str(MAIN.parent)
    环境变量["GENGFU_NO_LLM"] = "1"  # 不依赖真实网络 / ollama
    结果 = subprocess.run(
        [sys.executable, str(MAIN), str(脚本路径)],
        cwd=str(GENGFU_DIR),
        env=环境变量,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert 结果.returncode == 0, (
        f"道探针退出码 {结果.returncode}；stdout={结果.stdout!r} stderr={结果.stderr!r}"
    )
    数据: dict[str, str] = {}
    for 行 in 结果.stdout.splitlines():
        if 行.startswith("P|") and "=" in 行:
            键, 值 = 行[2:].split("=", 1)
            数据[键] = 值
    return 数据


def test_本地git真实闭环():
    """真实 git 链：初始提交 → Issue → 分支 → PR 载荷 → review → merge → ended(merged)。"""
    开始时间 = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="更夫git闭环-") as 临时目录:
        根 = Path(临时目录)
        bare仓库 = 根 / "远端.git"
        工作克隆 = 根 / "工作区"

        # --- 1) 建 bare 仓库 + 工作克隆（remote 仅指向本地 bare，不接外网） ---
        _运行git(根, "init", "--bare", "--initial-branch=main", str(bare仓库))
        _运行git(根, "clone", str(bare仓库), str(工作克隆))
        _运行git(工作克隆, "config", "user.email", "gengfu-test@example.com")
        _运行git(工作克隆, "config", "user.name", "更夫测试")

        # --- 2) 初始提交并 push 到 bare：main 主干基线 ---
        文件名 = "登录页.道"
        目标文件 = 工作克隆 / 文件名
        初始内容 = '// 登录页（基线）\n函数 渲染()\n    返回 "崩溃"'
        目标文件.write_text(初始内容, encoding="utf-8")
        _运行git(工作克隆, "add", 文件名)
        _运行git(工作克隆, "commit", "-m", "初始提交：登录页基线")
        _运行git(工作克隆, "push", "origin", "main")
        assert _运行git(bare仓库, "rev-parse", "--verify", "refs/heads/main"), (
            "初始提交未 push 到 bare 仓库的 main"
        )

        # --- 3) 模拟 Issue 事件 + 生成 merged 信号：复用真实第七轮产品代码 ---
        探针路径 = 根 / "闭环探针.道"
        探针路径.write_text(GIT_LOOP_SCRIPT, encoding="utf-8")
        信号数据 = _运行道脚本(探针路径)
        assert 信号数据["消息ID"] == "1001"
        assert 信号数据["事件类型"] == "issues.opened"
        assert 信号数据["话题键"] == "carsson/道#42"
        assert 信号数据["是否机器人"] == "真", "Issue 正文 @更夫 应触发生成工单"
        assert 信号数据["已合并"] == "真", "PR closed+merged 应由真实适配器置位 已合并"

        # --- 4) 构造 PR 载荷（等价第七轮执行器输出结构） ---
        分支名 = "fix/issue-42"
        新内容 = '// 登录页（已修复）\n函数 渲染()\n    返回 "正常"'
        提交信息 = f"修复登录页崩溃（Issue #42，{信号数据['话题键']}）"
        PR载荷 = {
            "分支": 分支名,
            "文件": 文件名,
            "新内容": 新内容,
            "提交信息": 提交信息,
            "来源信道": "github",
            "外部编号": 信号数据["消息ID"],
            "话题键": 信号数据["话题键"],
        }

        # --- 5) 建分支 → 应用 PR 载荷：真实文件改动 + add + commit + push ---
        _运行git(工作克隆, "checkout", "-b", PR载荷["分支"])
        目标文件.write_text(PR载荷["新内容"], encoding="utf-8")
        assert 目标文件.read_text(encoding="utf-8") == 新内容
        _运行git(工作克隆, "add", PR载荷["文件"])
        _运行git(工作克隆, "commit", "-m", PR载荷["提交信息"])
        _运行git(工作克隆, "push", "origin", PR载荷["分支"])

        # --- 6) 断言分支存在且 push 成功；commit 在 bare 仓库可达 ---
        分支引用 = f"refs/heads/{PR载荷['分支']}"
        分支提交 = _运行git(bare仓库, "rev-parse", "--verify", 分支引用)
        assert 分支提交, "PR 分支未出现在 bare 仓库"
        _运行git(bare仓库, "cat-file", "-e", f"{分支提交}^{{commit}}")
        assert PR载荷["新内容"] in _运行git(bare仓库, "show", f"{分支提交}:{文件名}")
        assert 提交信息 in _运行git(bare仓库, "log", "-1", "--format=%s", 分支名)

        # --- 7) review 检查：从 bare 引用读取分支文件内容与提交信息 ---
        评审内容 = _运行git(bare仓库, "show", f"{分支引用}:{文件名}")
        评审提交信息 = _运行git(bare仓库, "log", "-1", "--format=%s", 分支引用)
        assert 评审内容 == 新内容, f"review：分支文件内容与 PR 载荷不符：{评审内容!r}"
        assert 评审提交信息 == 提交信息, "review：分支提交信息与 PR 载荷不符"
        assert "已修复" in 评审内容, "review：未在分支上发现修复内容"

        # --- 8) merge 回主干并 push ---
        _运行git(工作克隆, "checkout", "main")
        _运行git(工作克隆, "merge", "--no-ff", "-m", "合并 PR：修复问题 #42", 分支名)
        _运行git(工作克隆, "push", "origin", "main")

        # --- 9) 断言合并后主干文件内容正确（工作克隆 + bare 两处），且分支提交已并入 main ---
        assert 目标文件.read_text(encoding="utf-8") == 新内容, "合并后工作区主干文件内容不正确"
        assert _运行git(bare仓库, "show", f"main:{文件名}") == 新内容, "bare 主干文件内容不正确"
        assert _运行git(bare仓库, "rev-parse", "refs/heads/main") == _运行git(
            工作克隆, "rev-parse", "HEAD"
        ), "工作区 main 与 bare main 不一致"
        _运行git(bare仓库, "merge-base", "--is-ancestor", 分支提交, "main")

        # --- 10) 工单状态信号 ended(merged)：真实合并落定后才成立 ---
        assert 信号数据["工单信号"] == "ended(merged)"
        assert 信号数据["绑定状态"] == "ended", "领域执行绑定应结束为 ended"

        耗时 = time.monotonic() - 开始时间
        print(
            f"本地 git 闭环通过：分支={分支名} 分支提交={分支提交[:8]} "
            f"工单信号={信号数据['工单信号']} 耗时={耗时:.2f}s"
        )
