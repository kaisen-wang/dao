# 更夫 Nightwatch — 生产进程守护部署说明（第八轮 · 配置样例）

> 本目录只提供 **systemd / supervisor 配置模板与部署说明**，不含任何产品代码改动。
> 所有路径目前指向本机开发目录，**未做真实云主机部署验证**；详见文末「诚实边界」。

## 1. 文件清单

| 文件 | 作用 |
| --- | --- |
| `systemd/更夫.service` | systemd 单元模板：`Restart=always` 拉起、日志交给 journald |
| `supervisor/更夫.conf` | 与上面等价的 supervisor 程序配置 |
| `README.md` | 本文件：安装步骤、环境变量、端口、兜底方案、边界说明 |

## 2. 前置假设

- Python 解释器：`/home/carson/code/test/道/源码/.venv/bin/python`（当前为软链，生产必须替换）。
- 解释器入口：`/home/carson/code/test/道/源码/main.py`。
- 道语言入口脚本：`/home/carson/code/test/道/示例/更夫/接入层/入口.道`。
- 工作目录：`/home/carson/code/test/道/示例/更夫`。**不可改**：道语言模块搜索基于 `os.getcwd()`，
  改为其它目录会导致 `从 基础设施层.存储 导入 ...` 等相对导入失败。
- 上面 `main.py` 不可省：道脚本直接交给 `python` 会触发 `SyntaxError`，必须由解释器载入。

## 3. 安装与启用

### 3.1 systemd

模板意图命令（单元名 `更夫`）：

```bash
sudo cp 部署/systemd/更夫.service /etc/systemd/system/更夫.service
sudo systemctl daemon-reload
sudo systemctl enable --now 更夫        # 开机自启 + 立即启动
systemctl status 更夫                    # 查看状态
journalctl -u 更夫 -f                   # 跟踪日志
# 重启 / 停止：sudo systemctl restart 更夫 / sudo systemctl stop 更夫
```

**但本机实测（systemd 259）：中文单元文件名会被拒绝**，`systemd-analyze verify /tmp/更夫.service`
报 `Failed to prepare filename ... 无效的参数`。因此真实安装请把文件改名为 ASCII 单元名后再启用：

```bash
sudo cp 部署/systemd/更夫.service /etc/systemd/system/gengfu.service
sudo systemctl daemon-reload
sudo systemctl enable --now gengfu      # 实测可用的 ASCII 单元名
systemctl status gengfu
journalctl -u gengfu -f
```

安装前请先按现场修改 unit 中的 `ExecStart` 解释器路径、`User`、`WorkingDirectory` 与环境变量值。

### 3.2 supervisor

```bash
sudo cp 部署/supervisor/更夫.conf /etc/supervisor/conf.d/更夫.conf
supervisorctl reread
supervisorctl update
supervisorctl start 更夫
supervisorctl status 更夫
# 重启 / 停止：supervisorctl restart 更夫 / supervisorctl stop 更夫
```

## 4. 日志位置

| 守护方式 | 标准输出 | 错误输出 | 查看命令 |
| --- | --- | --- | --- |
| systemd | journald（`StandardOutput=journal`） | journald（`StandardError=journal`），标识 `SyslogIdentifier=更夫` | `journalctl -u 更夫 -f` |
| supervisor | `/var/log/supervisor/更夫.stdout.log` | `/var/log/supervisor/更夫.stderr.log` | `supervisorctl tail -f 更夫 stdout` |

supervisor 日志按 `50MB` 轮转、保留 5 份；目录需现场创建并确保运行账号可写。

## 5. 环境变量表

| 变量 | 示例值 | 作用 | 被谁读取 |
| --- | --- | --- | --- |
| `GENGFU_NO_LLM` | `1` | 置 `1` 关闭本地 ollama，走关键词规则 + 模板报告降级路径，便于无模型服务运行 | `接入层/入口.道` |
| `更夫端口` | `8765` | 看板 HTTP 服务监听端口 | `看板服务.道` |
| `更夫数据库` | `/var/lib/gengfu/gengfu.db` | SQLite 持久化路径；默认 `:memory:` 仅内存，生产应给绝对路径 | `入口.道`/`守护.道`/`看板服务.道` |
| `更夫Webhook端口` | `8766` | Webhook 回调服务监听端口 | `webhook服务.道` |
| `更夫演示模式` | `0` | 默认（非 `0`）放宽白名单便于演示；置 `0` 启用生产白名单（初始仅 AI 本人） | `接入层/入口.道` |

此外 `webhook服务.道` 还用到 `更夫Webhook会话库`、`更夫飞书应用ID`、`更夫飞书应用密钥`、
`更夫企微应用ID`、`更夫企微token`；真实接入时按现场补齐，本模板不预置密钥。

### 5.1 systemd 中文变量名限制（重要）

本机 `systemd 259` 实测：`Environment=` 只接受 ASCII 变量名（ `[A-Za-z_][A-Za-z0-9_]` ），
上面 4 个中文变量名会被判定为 `Invalid environment assignment, ignoring`，**不会真正进入进程环境**
（`EnvironmentFile=` 同样不生效，已实测）。unit 中保留这些行是为了表达配置意图与满足契约；
若需让中文变量真正生效，请用包装脚本 `export` 后再 `exec` 同一条绝对 Python 命令：

```sh
#!/bin/sh
# /opt/gengfu/更夫启动.sh（chmod +x；生产路径与值按现场修改）
export GENGFU_NO_LLM=1
export 更夫端口=8765
export 更夫数据库=/var/lib/gengfu/gengfu.db
export 更夫Webhook端口=8766
export 更夫演示模式=0
cd /home/carson/code/test/道/示例/更夫 || exit 1
exec /home/carson/code/test/道/源码/.venv/bin/python \
     /home/carson/code/test/道/源码/main.py \
     /home/carson/code/test/道/示例/更夫/接入层/入口.道
```

然后把 unit 的 `ExecStart` 改为 `/opt/gengfu/更夫启动.sh`，其余项（WorkingDirectory、Restart 等）不变。
**supervisor 不受此限制**：其 `environment=` 会直接把字典交给子进程，中文变量名可生效。

## 6. 端口说明

| 端口 | 服务 | 入口脚本 | 状态 |
| --- | --- | --- | --- |
| 8765 | 看板服务（`/`、`/审计`、`/预算`、`POST /暂停` 等） | `看板服务.道` | 独立可启动 |
| 8766 | Webhook 回调（`POST /webhook/feishu`、`POST /webhook/wecom`） | `webhook服务.道` | 独立可启动，本地模式放行验签（真实平台必须关闭） |

注意：当前模板 `ExecStart` 指向的 `接入层/入口.道` 是**端到端演示入口**，运行完演示后正常退出（退出码 0），
本身不监听上述端口；配合 `Restart=always` 会退出后再次拉起。生产部署应把 `ExecStart` 换成实际长驻入口
（如 `看板服务.道`、`webhook服务.道`，或由包装脚本同时编排），或按实际形态调整 `Type=`。
这是配置样例的已知限制，需现场确认，本轮未改为真实长驻服务入口。

## 7. 轮询兜底说明（PRD NFR「轮询兜底容忍 webhook 丢失」）

**目标**：webhook 是事件主路径，但平台回调可能失败或丢失；需要定时轮询从事件源补事件，
并保证补事件不重复建单。

**现状**：`webhook服务.道` 已提供重放防护（重复事件返回 `409 重复事件`）与归一化回调桥接，
但**没有定时轮询组件**。webhook 一旦丢投，对应事件不会被自动补达。

**本轮方案（仅说明，未实现代码）**：

1. 在宿主机加一个定时任务：`systemd timer`（推荐 `更夫轮询兜底.timer` + 配套 oneshot service）
   或 cron，周期 1–5 分钟。
2. 作业按时间窗口（例如回看 10 分钟，容忍时钟偏差）主动拉取事件源近期事件：
   GitHub Issues/PR、飞书/企微会话历史等。
3. 拉取到的事件复用与 webhook 相同的归一化与 `创建Webhook桥接` 回调送入 L3 Router；
   用「外部编号 + 幂等键」去重，避免与已成功 webhook 的事件重复建单。
4. 失败重试并告警；轮询与 webhook 并行，webhook 仍为主路径，轮询只做补漏。
5. 真实事件源客户端与密钥需在接入真实平台时补齐；**本轮不接真实 GitHub / 飞书 / 企微，
   未新增任何 timer / cron 文件，未实现定时轮询代码**。

## 8. 与既有 `守护.道` 的关系

两者是**互补的两层守护**，互不替代：

- **外层（systemd / supervisor）**：OS 级进程守护。负责开机自启、进程崩溃或被 `kill` 后拉起、
  日志采集；只判断「进程是否还活着」。
- **内层（`守护.道` 轻量心跳）**：道语言业务级观测。每 5 秒（`周期执行(5000, 心跳)`）
  输出单调时间戳与工单/触发/决策统计，异常捕获后继续运行；进程活着但业务停滞时，
  可从心跳中断或统计不再变化看出问题。
- 边界：`守护.道` 无进程 fork 原语，**不能自行拉起进程**，异常时只能继续运行并观测；
  崩溃拉起必须依赖外层 systemd/supervisor。反过来，外层无法感知业务级停滞，
  必须靠内层心跳/统计提供观测信号。

## 9. 诚实边界

- **未做真实云主机部署验证**：本目录所有路径、账号、端口均为本机样例值。
- systemd / supervisor 文件是**配置样例**，真实账号、权限、网络、日志目录、白名单与密钥需现场配置。
- **不宣称 DoD 通过**：按共享契约 §3，本轮最多在注记中写「本地真实部分已验证」，
  PRD §12 相关项整项 DoD 继续保持未勾选。
- 本轮不接真实 GitHub / 飞书 / 企微、不发真实网络请求、未实现定时轮询代码。
- `.venv` 软链指向开发机 runtime；生产必须替换为真实解释器路径。
- `Environment=` 中文变量名在 systemd 下不生效（见 5.1），已给出包装脚本方案但本模板未默认启用。
- **systemd 259 拒绝中文单元文件名**：`systemd-analyze verify .../更夫.service` 直接失败；
  改名为 ASCII 文件名后语法可校验通过。生产必须使用 ASCII 单元名（如 `gengfu.service`）。

## 10. 自检记录（本机，2026-11-22）

路径存在性（`pathlib.Path(...).exists()`）：

```text
WorkingDirectory 目录: exists=True is_dir=True  通过=True -> /home/carson/code/test/道/示例/更夫
入口脚本 文件:         exists=True is_file=True 通过=True -> /home/carson/code/test/道/示例/更夫/接入层/入口.道
Python 解释器 文件:    exists=True is_file=True 通过=True -> /opt/workbuddy/resources/runtime/python/bin/python3.13
解释器 main.py 文件:   exists=True is_file=True 通过=True -> /home/carson/code/test/道/源码/main.py
结论: 全部路径真实存在且类型正确；退出码=0
```

systemd unit 语法（`systemd-analyze verify`）：

```text
# 中文文件名（交付文件名）直接校验失败：
$ systemd-analyze verify /tmp/更夫.service
Failed to prepare filename /tmp/更夫.service: 无效的参数
退出码=1

# 同一内容改为 ASCII 文件名后可解析（仅 4 行中文变量名被忽略，见 5.1）：
$ systemd-analyze verify /tmp/gengfu-ascii.service
/tmp/gengfu-ascii.service:39: Invalid environment assignment, ignoring: 更夫端口=8765
/tmp/gengfu-ascii.service:40: Invalid environment assignment, ignoring: 更夫数据库=/var/lib/gengfu/gengfu.db
/tmp/gengfu-ascii.service:41: Invalid environment assignment, ignoring: 更夫Webhook端口=8766
/tmp/gengfu-ascii.service:42: Invalid environment assignment, ignoring: 更夫演示模式=0
退出码=0
```

supervisor INI 语法（`configparser`）：

```text
读取文件: ['部署/supervisor/更夫.conf']
sections: ['program:更夫']
command: /home/carson/code/test/道/源码/.venv/bin/python /home/carson/code/test/道/源码/main.py /home/carson/code/test/道/示例/更夫/接入层/入口.道
directory: /home/carson/code/test/道/示例/更夫
autostart/autorestart/startsecs: true true 5
environment: GENGFU_NO_LLM=1,更夫端口=8765,更夫数据库=/var/lib/gengfu/gengfu.db,更夫Webhook端口=8766,更夫演示模式=0
全部必需字段与环境变量校验通过；退出码=0
```

结论：三个文件均已落盘；路径真实存在；unit 内容语法可解析，但中文单元文件名与中文环境变量名在
本机 systemd 259 下均不被接受（已如实记录并给出 ASCII 改名 / 包装脚本方案）；
supervisor INI 语法与必需字段全部通过。本轮**未做真实云主机部署验证，不宣称 DoD 通过**。
