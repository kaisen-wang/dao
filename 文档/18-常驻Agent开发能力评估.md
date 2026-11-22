# 18. 用道语言开发「常驻研发协作 Agent」的能力评估

> 更新：2026-11-22。对照 `任务/常驻研发协作 Agent.md`（PRD v0.1，代号「更夫 Nightwatch」），盘点道语言现有运行时与标准库能力，给出缺口清单、补齐顺序与架构取舍。
>
> **结论**：语言本身不是瓶颈。HTTP 服务端/客户端、异步子进程、文件 IO、JSON、正则、环境变量、日志、协程并发均已具备，写端到端原型没有障碍。原阻塞 v1.0 的 **SQLite 持久化、HMAC/哈希/UUID、定时调度、HTTP 服务端并发** 四项已于 2026-11-21 全部补齐（见 18.9）；剩余缺口集中在 GitHub/LLM 协议封装、Web 面板与工程脚手架，属业务工程而非语言能力。

## 18.1 评估范围与方法

评估对象为 `源码/dao/` 下的标准库（14 个导出模块，含本轮新增的密码/数据库/调度）、内置函数（33 个基础 + 15 个高阶）、并发包与 AI 示例。核验方式为逐文件读取 + 全局 grep 关键字（`sqlite|hashlib|hmac|uuid|cron` 等），不以概述文档为准。文中行号以 2026-11-22 代码为准。

对照的 PRD 需求为 FR-01～FR-18，其中 v1.0 必须交付的为 FR-01～FR-15。

## 18.2 现成可用的能力

| 能力 | 证据位置 | 对 PRD 的支撑 |
|---|---|---|
| HTTP 客户端（`请求` / `流式请求`） | `dao/stdlib/network.py:218-316`，支持方法/请求头/数据/超时、NDJSON 逐行回调 | LLM 与 GitHub API 调用、Outbox 投递、受阻通知 |
| HTTP 服务端（`创建服务器`） | `dao/stdlib/network.py:54-215`，`路由` + `启动` + `关闭`，ThreadingHTTPServer 并发、前缀通配路由、1MB Body 上限，`请求.JSON()` | webhook 接收、Web 面板底座 |
| 哈希与验签 | `dao/stdlib/crypto.py`，`SHA256`/`HMACSHA256`/`验证HMAC`/`UUID`/`随机令牌` | webhook 验签、幂等键、去重 |
| SQLite 持久化 | `dao/stdlib/db.py`，`连接` + 线程锁保护的连接对象，执行/查询/事务/WAL | FR-13 领域对象落库与崩溃恢复 |
| 定时调度 | `dao/stdlib/schedule.py`，延迟/周期执行、取消、等待，支持道语言回调 | FR-01 轮询兜底、FR-16 Watchdog、预算日重置 |
| 同步子进程（`系统.执行命令`） | `dao/stdlib/system.py:37-53`，shell + stdout/stderr + 60s 超时 | git worktree、跑测试 |
| 异步子进程（`异步IO.创建子进程`） | `dao/stdlib/asyncio.py:544-619`，退出码、终止/杀死、通信 | FR-09 异步工具的 start/stop |
| 文件与目录 IO | `dao/stdlib/file.py:35-141`，读写/追加/列目录/复制/移动/删除/建目录/文件信息 | worktree 管理、配置读写 |
| JSON 编解码 | `dao/stdlib/encoding.py:12-38`，`JSON.编码/解码`，响应对象另有 `.JSON()` | webhook payload、LLM 消息 |
| 正则 | `dao/stdlib/text.py:99-120`，`正则匹配`/`分割全部`/`替换全部`（带编译缓存） | FR-02 规则匹配、FR-03 规则判断 |
| 环境变量 | `dao/stdlib/system.py:14-29`，`取环境变量`/`设环境变量` | 凭据注入，不进模型上下文 |
| 日志与 stderr | `dao/stdlib/log.py`、`dao/builtins/functions.py:44-54`（`错误输出`） | 审计流水、不污染 stdout |
| 协程与同步原语 | `并行` 语法、`dao/concurrency/`（通道/锁/信号量/协程池）、`异步IO` 任务 API | FR-10 Slot 调度、FR-08 并行 Worker |
| 基础并发计数 | 内置 `原子整数`/`原子布尔`/`互斥锁`（`functions.py:265-283`） | FR-12 成本熔断计数 |
| LLM 调用先例 | `示例/AI对话/`，`网络.请求` + `编码.JSON` 调 ollama `/api/chat`、`/api/tags` | Eval 与 Worker 的调用范式 |

## 18.3 原阻塞 v1.0 的四个缺口（均已补齐）

> 本节保留原始评估结论与补齐方案作为决策依据；实际落地情况见 18.9。

### 18.3.1 SQLite 持久化（原最大缺口）— 已补齐

FR-13 要求全部领域对象（Trigger / Thread / Ticket / Assignment / Report / Outbox）与会话落 SQLite WAL，`kill -9 ×10` 恢复率 100%。原状态：`dao/stdlib/` 无任何 DB 模块，`requirements.txt` 无数据库依赖，全局 grep `sqlite|sqlalchemy|redis` 在 `dao/` 下零命中。

**补齐方式（已实施）**：新建 `dao/stdlib/db.py`，照 `file.py` 的 `create_module_env()` + `env.define()` 模式封装 Python 标准库自带的 `sqlite3`，暴露连接、执行、查询全部行、事务提交/回滚、WAL 开关，并在 `registry.py` 注册。属薄封装，未新增 pip 依赖。

### 18.3.2 HMAC / 哈希 / UUID — 已补齐

FR-01 要求按 `(source, external_id)` 去重，FR-11 要求 Outbox 幂等键，§10 安全要求 GitHub webhook 验签（`X-Hub-Signature-256`）。原状态：全局 grep `hashlib|hmac|uuid|secrets|sha256` 在 `dao/` 下零命中，webhook 签名验证在道语言层做不了。

**补齐方式（已实施）**：新建 `dao/stdlib/crypto.py` 薄封装 `hashlib`/`hmac`/`uuid`/`secrets`，暴露 SHA-256、HMAC-SHA256、UUID4、常量时间比较与随机令牌。

### 18.3.3 定时调度 — 已补齐

FR-01 轮询兜底 60s、FR-16 Watchdog 30 分钟内发现停滞、FR-12 日预算重置都需要定时能力。原状态：只有阻塞式 `睡眠` 和测耗时的 `DaoTimer`（`time.py:87-102`）与内置 `时间戳`，没有 cron / `call_later` / `Timer`。

**补齐方式（已实施）**：新建 `dao/stdlib/schedule.py`，基于 `threading.Timer` 暴露 `延迟执行(毫秒, 回调)` / `周期执行(毫秒, 回调)` / `取消调度` / `取消全部` / `等待全部`，支持道语言函数回调。

### 18.3.4 HTTP 服务端单线程 — 已补齐

原状态：`network.py` 使用 `HTTPServer.serve_forever()` 与精确路由匹配（无通配与参数），webhook、Web 面板与审计流会串行排队，而 NFR 要求 webhook→建单 ≤10s。

**补齐方式（已实施）**：换用 `http.server.ThreadingHTTPServer`（`network.py:93-196`），补前缀通配路由、1MB Body 上限（超限 413）与 `关闭()`。旧测试的 `patch("http.server.HTTPServer")` 通过兼容 shim 保持有效。`异步IO.启动服务器`（`asyncio.py:705`）仍是 TCP 层回调，未用于 HTTP。

### 18.3.5 附带问题：退出码不可结构化获取 — 保持原状

`系统.执行命令`（`system.py:47-48`）在非 0 退出时直接抛 `运行时错误`，拿不到退出码。FR-08 要求把验证结果写入 PR 报告，Worker 应改用 `异步IO.创建子进程` 的 `等待()` → 退出码 / `通信()` → `(stdout, stderr)`。本项未改语言层，属调用方选择。

## 18.4 有原语但没有预制件的部分

| 缺口 | 说明 | 性质 |
|---|---|---|
| GitHub API 封装 | 分页、条件请求、速率限制仍需用 `网络.请求` + `编码.JSON` 手写；**webhook 验签原语已具备**（`密码.验证HMAC`），只差封装为 GitHub 事件适配器 | 业务工程 |
| LLM 工具调用协议 | 现有示例仅朴素 `/api/chat`；Worker 需要 Function Calling / Tool Use 的结构化往返与六类报告协议 | 业务工程 |
| Web 面板渲染 | 无模板引擎、无静态文件服务，HTML 需手写或再补模块 | 业务工程 |
| 进程守护与崩溃恢复 | 解释器本身不是 daemon，7×24 与 `kill -9` 恢复需外层 systemd/supervisor，道语言只写恢复逻辑 | 部署工程 |
| 压测与混沌脚手架 | §12 的 300 消息合成负载、kill -9 / 断网 / 重复投递 ×10 无现成 harness | 测试工程 |

这些不是语言缺陷，而是"标准库给了砖、没有预制板"。不宜为了一个项目把它们全部塞进语言核心。

## 18.5 PRD 需求 → 能力映射

| 需求 | 状态 | 说明 |
|---|---|---|
| FR-01 事件接入 | 部分→基本具备 | HTTP 并发服务端 + 通配路由 + 验签原语（`密码.验证HMAC`）+ 去重键（`UUID`/`随机令牌`）均已有；只差 GitHub 适配器封装 |
| FR-02 准入矩阵 | 有 | 条件/字典/正则齐备 |
| FR-03 语义评估 Eval | 部分 | JSON 与 HTTP 有；工具调用协议缺 |
| FR-04 三级执行模式 | 有 | 条件与状态表达齐备 |
| FR-05 不可变授权 | 有 | 冻结集合 + `数据库` 落库均具备 |
| FR-06 Thread⇄Ticket 订阅 | 有 | 字典/集合数据结构齐备 |
| FR-07 重开规则 | 有 | 条件判断齐备 |
| FR-08 Worker 与报告 | 部分 | 子进程有；结构化退出码需换异步 API |
| FR-09 异步工具 | 有 | 异步子进程 + 任务 API |
| FR-10 Slot 调度 | 有 | 信号量/队列/并行语法 |
| FR-11 PR 交付 + Outbox | 有 | HTTP 客户端 + 幂等键原语（`UUID`/`随机令牌`）齐备 |
| FR-12 成本熔断 | 有 | 原子整数可计数 + `调度.周期执行` 可做日预算重置 |
| FR-13 持久化恢复 | 有 | `数据库` 模块提供 SQLite WAL + 事务；恢复逻辑仍需业务层实现 |
| FR-14 Web 面板 | 部分 | HTTP 骨架有；模板与静态服务缺 |
| FR-15 受阻通知 | 有 | HTTP 客户端可用 |
| FR-16 Watchdog | 有 | `调度.周期执行` 可做停滞巡检（P1） |
| FR-17 常驻 Router | 部分 | 全局记忆可落 `数据库`；跨会话逻辑仍需业务层实现 |
| FR-18 IM 适配器 | 有 | HTTP 客户端可用 |

## 18.6 补齐顺序建议

| 时点 | 补什么 | 状态 | 量级 |
|---|---|---|---|
| v0.1 前 | `db.py`（SQLite WAL）+ `crypto.py`（哈希/HMAC/UUID）+ 服务端并发化 | **已完成**（2026-11-21，见 18.9） | 三项 100～200 行 Python 薄封装 |
| v0.2 前 | 定时调度器 + GitHub webhook 验签封装 | 调度器**已完成**；验签原语已具备（`密码.验证HMAC`），待封装为 GitHub 适配器 | 中 |
| v1.0 前 | LLM 工具调用协议层 + Web 面板 + 守护/压测脚手架 | 未开始 | 大，属业务工程而非语言能力 |

## 18.7 架构取舍

两种路线，建议按目标选择：

1. **验证架构可行性**：直接用现有能力写最小闭环。语言层底座已备齐，可以直接进入 Agent 业务开发。
2. **全栈道语言交付 v1.0**：语言层缺口已补齐（新增 3 个模块、约 1000 行封装 + 53 个测试），可以开始写 Agent 业务。

架构取舍上，原先建议「Python 宿主承担 SQLite、调度、守护」的混合架构，前提不成立——`数据库`/`调度` 已在道语言层提供中文 API，无需再留 Python 宿主。**当前建议**：核心业务（Eval 规则、策略脚本、报告生成、事件流）用道语言写，与 LSP 的取舍仍一致（生产用 `dao/lsp/` Python 版，道语言版作自举旗舰）；但**进程守护、崩溃恢复的宿主管控**仍留在 Python/系统层——解释器本身不是 daemon，这部分不属语言能力问题。

## 18.8 附：核验证据索引

- 标准库注册表：`dao/stdlib/registry.py:20-51`（14 个模块）
- HTTP 服务端：`dao/stdlib/network.py:54-215`（`DaoHttpServer`）；HTTP 客户端：`218-316`
- 新增三模块：`dao/stdlib/crypto.py`、`db.py`、`schedule.py`（工厂分别在 67 / 144 / 212 行）
- 系统原语：`dao/stdlib/system.py:14-53`
- 异步子进程与 TCP 服务器：`dao/stdlib/asyncio.py:544-619`、`690-726`
- 内置函数表：`dao/builtins/functions.py:365-401`（33 基础）；`hof.py`（15 高阶）
- 并发原语：`dao/concurrency/`（channels / sync / coroutines / selectors）
- LLM 调用先例：`示例/AI对话/`（`单次问答.道`、`流式对话.道`、`使用说明.md`）

## 18.9 实现进展（2026-11-21，并行开发第一轮）

v0.1 前的语言层缺口已全部补齐。采用四个子代理并行开发、主代理独占共享注册表与文档的方式，按文件范围隔离：

| 缺口 | 交付文件 | 成果 |
|---|---|---|
| HMAC / 哈希 / UUID | `dao/stdlib/crypto.py`、`tests/test_stdlib/test_crypto.py` | 新增「密码」模块：`SHA256`、`HMACSHA256`、`验证HMAC`（常量时间比较）、`UUID`、`随机令牌` |
| SQLite 持久化 | `dao/stdlib/db.py`、`tests/test_stdlib/test_db.py` | 新增「数据库」模块：`连接` 返回受线程锁保护的连接对象，含执行/查询/事务/WAL/关闭 |
| 定时调度 | `dao/stdlib/schedule.py`、`tests/test_stdlib/test_schedule.py` | 新增「调度」模块：`延迟执行`、`周期执行`、`取消调度`、`取消全部`、`等待全部`，支持道语言函数回调 |
| HTTP 服务端并发 | `dao/stdlib/network.py`、`tests/test_stdlib/test_network_server.py` | `ThreadingHTTPServer` + 前缀通配路由 + 1MB Body 上限（超限 413）+ 可关闭 |

**集成改动**：`dao/stdlib/registry.py` 注册三个新模块（14 个模块）；`tests/test_docgen_stdlib.py` 模块数断言 11→14、文档数 13→16；`文档/10-标准库.md` 与 `文档/标准库API/README.md` 同步模块清单；新增三份 API 文档。

**架构约束遵循**：新函数均为模块级定义并带中文 docstring，满足 docgen 元数据幂等要求；回调型内置用 `InterpreterBuiltin` 取得解释器上下文，与 `流式请求` 范式一致；全部仅依赖 Python 标准库，未新增 pip 依赖。

**验收（2026-11-21，主代理独立实测）**：

- 全量测试：`cd 源码 && ./.venv/bin/python -m pytest tests/ -q` → **1490 passed / 2 skipped / 3 warnings**（较第八轮基线 1429 增加 61 项）。
- 静态检查：新增与修改的 11 个文件 `ruff check` → **All checks passed**（`F821`/`E9` 专项亦全绿）。
- 网络回归：`test_network.py` + `test_network_stream.py` + `test_network_server.py` 共 52 passed；旧测试用 `patch("http.server.HTTPServer")` 拦截创建，改造后仍兼容。
- 模块数 11 → 14，docgen 文档数 13 → 16，两处硬编码断言已同步。
- 集成中发现并修复：调度模块缺 `BuiltinFunction` 导入导致 docgen 崩溃、适配器函数缺中文 docstring、注册表导入排序、docgen 数量断言（两个测试文件）。

**提交记录**（2026-11-21，main 分支，未 push）：`24c69f4`（核心代码 + 测试，11 文件）、`f66928a`（PRD + 文档 18 + API 文档，7 文件）、`cd5acdd`（Phase2 清单同步，2 文件）。提交后复核全量测试仍为 1490 passed / 2 skipped，工作区干净。

**下一轮待做**（对应 18.6 的 v0.2/v1.0）：

1. GitHub webhook 事件适配器——验签原语（`密码.验证HMAC`）与并发服务端已具备，只差把 payload 归一化为 Trigger 的封装；
2. LLM 工具调用协议层（Function Calling / Tool Use + 六类报告）；
3. Web 面板模板/静态服务与进程守护、压测/混沌脚手架。

以上均属业务工程，不需要再改语言层。
