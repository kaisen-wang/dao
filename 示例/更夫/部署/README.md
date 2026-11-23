# 更夫 Nightwatch — 生产进程守护部署说明（第九轮 · 生产守护收口）

> 本目录只提供 **systemd / supervisor 配置、启动包装脚本与部署说明**，不含产品核心代码改动。
> 第九轮收口第八轮遗留的四个缺口：① systemd 中文单元名被拒 → ASCII 单元名；② 中文环境变量名被拒 →
> 启动包装脚本 export；③ 演示入口跑完即退 → 长驻入口；④ 轮询兜底只有方案 → 组件化 + 定时封装。
> 所有路径均为 `/opt/gengfu` 占位样例，**未做真实云主机部署验证**；详见文末「诚实边界」。

## 1. 文件清单

| 文件 | 状态 | 作用 |
| --- | --- | --- |
| `systemd/gengfu.service` | **第九轮新建（生产用）** | ASCII 单元名；`Restart=always` 拉起；日志交 journald；`ExecStop` 触发优雅停机 |
| `systemd/启动包装.sh` | **第九轮新建（生产用）** | ASCII 中转变量 → export 五个中文变量 → `exec` 长驻入口 |
| `supervisor/gengfu.conf` | **第九轮新建（生产用）** | 与上面等价的 supervisor 程序配置，ASCII program 名 `gengfu` |
| `systemd/更夫.service` | 历史样例（保留不动） | 第八轮配置样例，记录了 systemd 259 对中文单元名/中文变量名的限制分析 |
| `supervisor/更夫.conf` | 历史样例（保留不动） | 第八轮 supervisor 样例 |
| `README.md` | 本文件 | 安装步骤、包装脚本原理、环境变量、轮询兜底、边界说明 |

> 中文原文件 `更夫.service` / `更夫.conf` **保留作为历史样例**（含 systemd 限制分析）；
> **生产部署一律使用 ASCII 版 `gengfu.service` / `gengfu.conf`**。

## 2. 前置假设与现场替换

- Python 解释器、解释器入口 `main.py`、工作目录 **均由启动包装.sh 以绝对路径占位**给出：
  - `GENGFU_PYTHON` 占位 `/opt/gengfu/venv/bin/python`（生产替换真实解释器）
  - `GENGFU_MAIN` 占位 `/opt/gengfu/源码/main.py`
  - `GENGFU_ROOT` 占位 `/opt/gengfu/示例/更夫`
  - 部署根 `/opt/gengfu/run/gengfu.stop` 为停机标记文件，需建目录且运行账号可写
- **不可改工作目录**：道语言模块搜索基于 `os.getcwd()`（cwd），切到其它目录会导致
  `从 基础设施层.存储 导入 ...` 等相对导入失败。
- `main.py` 不可省：`.道` 脚本直接交给 `python` 会触发 `SyntaxError`，必须由解释器载入。
- 长驻入口为 `接入层/常驻入口.道`（第九轮新增，主线程保活 + 优雅停机），
  **替代**跑完即退的演示入口 `接入层/入口.道`；后者配合 `Restart=always` 会循环拉起，不可用于生产。
- 包装脚本部署后执行 `chmod +x /opt/gengfu/示例/更夫/部署/systemd/启动包装.sh`。

## 3. 第九轮关键改动原理

### 3.1 ASCII 单元名

systemd 259 拒绝中文单元文件名（`systemd-analyze verify .../更夫.service` 报 `Failed to prepare filename ... 无效的参数`）。
生产使用 ASCII 名 `gengfu.service`，`enable --now gengfu` 可正常拉起。

### 3.2 启动包装脚本（中文变量落地）

systemd 259 的 `Environment=` 只接受 ASCII 变量名 `[A-Za-z_][A-Za-z0-9_]`；中文变量名会被判定为
`Invalid environment assignment, ignoring`，不会进入进程环境（`EnvironmentFile=` 同样无效）。
因此 unit 内**不写任何中文变量名**，改由 `systemd/启动包装.sh` 完成：

1. 先把值存入 ASCII 中转变量（`GENGFU_PORT` / `GENGFU_DB` / `GENGFU_WEBHOOK_PORT` / `GENGFU_DEMO` 等）；
2. 再 `export 更夫端口="$GENGFU_PORT"` 等五个中文变量，使中文变量真正进入进程环境；
3. `cd` 到 `示例/更夫` 后 `exec "$GENGFU_PYTHON" "$GENGFU_MAIN" "接入层/常驻入口.道"`。

> supervisor 不受此限制：其 `environment=` 直接把字典交给子进程，中文变量名可生效，
> 但为统一口径，supervisor 的 `command` 也指向同一包装脚本。

### 3.3 长驻入口 + 优雅停机标记

- 长驻入口 `接入层/常驻入口.道` 用 `调度.周期执行` 注册 5 秒心跳（保活 + 统计），不会跑完即退。
- 优雅停机：向停机标记文件写标记即触发退出。systemd 的 `ExecStop` 为
  `/bin/sh -c 'touch /opt/gengfu/run/gengfu.stop'`，心跳检测到该标记后取消全部调度并退出循环。
- 标记路径由环境变量 `更夫停机标记` 指定（默认 `/tmp/gengfu.stop`）；生产须把它设为与 `ExecStop`
  同一路径 `/opt/gengfu/run/gengfu.stop`（包装脚本与 supervisor `environment` 均已如此配置）。

### 3.4 轮询兜底启用方式（本地注入模拟源）

轮询兜底组件位于 `基础设施层/轮询兜底.道`（L1），只做「事件源拉取 + SHA256 幂等去重 + 回调派发」，
回调复用 `webhook服务.创建Webhook桥接` 产出的回调，禁止反向依赖 L4。启用方式：

1. 事件源为**无参函数**，返回事件字典列表（本轮为本地注入的模拟源；真实 GitHub/飞书/企微客户端未接）。
2. 调用 `创建轮询兜底(事件源, 回调, 已见集合)` 得到轮询器；`已见集合` 外部传入可跨调用共享去重。
3. 调用 `创建定时轮询(轮询器, 间隔毫秒=60000)` 用 `调度.周期执行` 注册定时兜底，默认 60 秒一轮。
4. 在长驻入口 `接入层/常驻入口.道` 中可选注册该定时轮询；webhook 仍为主路径，轮询只做补漏。

> 「轮询兜底组件已实现」≠「真实平台补漏已验证」：本轮事件源全部为本地注入模拟源。

## 4. 安装与启用

### 4.1 systemd（生产用 ASCII 名 gengfu）

```bash
sudo cp 部署/systemd/gengfu.service /etc/systemd/system/gengfu.service
sudo chmod +x /opt/gengfu/示例/更夫/部署/systemd/启动包装.sh
sudo systemctl daemon-reload
sudo systemctl enable --now gengfu      # 开机自启 + 立即启动
systemctl status gengfu
journalctl -u gengfu -f                 # 跟踪日志
# 优雅停机：sudo systemctl stop gengfu   （ExecStop touch 停机标记，心跳感知后退出）
```

安装前按现场修改 unit 的 `ExecStart` / `ExecStop` / `WorkingDirectory` 路径，以及包装脚本内的解释器路径与变量值。

### 4.2 supervisor（生产用 ASCII 名 gengfu）

```bash
sudo cp 部署/supervisor/gengfu.conf /etc/supervisor/conf.d/gengfu.conf
sudo chmod +x /opt/gengfu/示例/更夫/部署/systemd/启动包装.sh
supervisorctl reread
supervisorctl update
supervisorctl start gengfu
supervisorctl status gengfu
# 重启 / 停止：supervisorctl restart gengfu / supervisorctl stop gengfu
```

## 5. 日志位置

| 守护方式 | 标准输出 | 错误输出 | 查看命令 |
| --- | --- | --- | --- |
| systemd | journald（`StandardOutput=journal`） | journald（`StandardError=journal`），标识 `SyslogIdentifier=gengfu` | `journalctl -u gengfu -f` |
| supervisor | `/var/log/supervisor/gengfu.stdout.log` | `/var/log/supervisor/gengfu.stderr.log` | `supervisorctl tail -f gengfu stdout` |

supervisor 日志按 50MB 轮转、保留 5 份；目录需现场创建并确保运行账号可写。

## 6. 环境变量表

| 变量 | 示例值 | 作用 | 来源 / 被谁读取 |
| --- | --- | --- | --- |
| `GENGFU_NO_LLM` | `1` | 关闭本地 ollama，走关键词规则 + 模板报告降级路径 | ASCII 变量，包装脚本直接 `export`；入口读取 |
| `更夫端口` | `8765` | 看板 HTTP 服务监听端口 | 中转 `GENGFU_PORT` → `export`；`看板服务.道` |
| `更夫数据库` | `/var/lib/gengfu/gengfu.db` | SQLite 持久化路径（默认 `:memory:` 仅内存，生产须绝对路径） | 中转 `GENGFU_DB`；入口/守护/看板服务 |
| `更夫Webhook端口` | `8766` | Webhook 回调服务监听端口 | 中转 `GENGFU_WEBHOOK_PORT`；`webhook服务.道` |
| `更夫演示模式` | `0` | 置 `0` 启用生产白名单（初始仅 AI 本人）；非 `0` 放宽便于演示 | 中转 `GENGFU_DEMO`；入口 |
| `更夫停机标记` | `/opt/gengfu/run/gengfu.stop` | 优雅停机标记文件路径，与 systemd `ExecStop` 指向同一文件 | 中转 `GENGFU_STOP_FILE`；长驻入口心跳 |

此外 `webhook服务.道` 还用到 `更夫Webhook会话库`、`更夫飞书应用ID`、`更夫飞书应用密钥`、
`更夫企微应用ID`、`更夫企微token`；真实接入时按现场补齐，本模板不预置密钥。

## 7. 端口说明

| 端口 | 服务 | 入口脚本 | 状态 |
| --- | --- | --- | --- |
| 8765 | 看板服务（`/`、`/审计`、`/预算`、`POST /暂停` 等） | `看板服务.道` | 独立可启动 |
| 8766 | Webhook 回调（`POST /webhook/feishu`、`POST /webhook/wecom`） | `webhook服务.道` | 独立可启动，本地模式放行验签（真实平台必须关闭） |

第九轮起 `ExecStart`/`command` 指向 `接入层/常驻入口.道`（长驻），不再指向跑完即退的演示入口.道。

## 8. 与既有 `守护.道` 的关系

两层守护互补、互不替代：

- **外层（systemd / supervisor）**：OS 级守护，负责开机自启、崩溃/kill 后拉起、日志采集；只判断「进程是否还活着」。
- **内层（`守护.道` 轻量心跳）**：道语言业务级观测，每 5 秒输出时间戳与工单/触发/决策统计，异常捕获后继续运行。
- 边界：`守护.道` 无进程 fork 原语，不能自行拉起进程；崩溃拉起依赖外层。外层无法感知业务级停滞，
  须靠内层心跳/统计提供观测信号。

## 9. 诚实边界

- **未做真实云主机部署验证**：所有路径、账号、端口、停机标记均为本机占位样例。
- **未接真实平台**：本轮事件源均为本地注入的模拟源；未接真实 GitHub / 飞书 / 企微，未发真实网络请求，
  真实 webhook 回调闭环 / 凭据 / CI / 真实工单状态回写均未做。
- **不勾选 DoD**：按共享契约，PRD §12 六项 DoD 全部继续保持未勾选，只在注记写「本地可验证部分已实现」。
- **本机无 `systemd-analyze`、无 pytest**：当前开发机为 Windows，无法运行 `systemd-analyze verify`
  或真实守护进程拉起；改用 `sh -n`（包装脚本语法）+ Python `configparser` 与文本断言（unit/supervisor 静态校验）替代，
  **不伪造这两类命令的结果**。
- 未做断网 ×10、真实外部消息 0 丢失 0 重复计数、≥1 周 observe 运行、开启 auto 模式。
- `.venv`/占位解释器路径按现场替换；生产务必用专用系统账号 `gengfu`，不要用 root。

## 10. 自检记录（本机静态校验）

本机为 Windows、无 systemd-analyze，按规约用静态校验替代，命令与输出见交付报告：

- 包装脚本语法：`sh -n "部署/systemd/启动包装.sh"` → 退出码 0。
- unit/supervisor：用本机 Python `configparser` 读取 `gengfu.conf` 与 `gengfu.service`，
  断言关键字段存在、unit 段无中文变量名、文件名 ASCII → 输出 PASS，退出码 0。

> 上述仅证明配置文本语法与字段口径正确，**不等价于真实 systemd/supervisor 拉起验证**。
