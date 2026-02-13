# Phase 3 并发编程开发计划

> **开发阶段**：Phase 3 - 并发编程  
> **开始时间**：2025年1月  
> **预计工期**：4-5周  
> **优先级**：高（Phase 3 第一个特性）

---

## 📋 目录

1. [概述](#概述)
2. [功能模块](#功能模块)
3. [任务分解](#任务分解)
4. [技术架构](#技术架构)
5. [实现步骤](#实现步骤)
6. [测试计划](#测试计划)
7. [示例程序](#示例程序)
8. [验收标准](#验收标准)

---

## 概述

### 目标

为道语言提供完整的并发编程支持，包括：

1. **异步/等待** - 基于 Python asyncio 的异步函数
2. **协程和通道** - 类似 Go 语言的并发模型
3. **同步原语** - 互斥锁、原子操作等

### 设计原则

- **安全性优先**：防止数据竞争和死锁
- **简单易用**：提供直观的语法
- **高效性能**：最小化运行时开销
- **Python 互操作**：与 Python 生态良好集成

### 技术选型

- **异步框架**：Python asyncio（内置，无需额外依赖）
- **协程实现**：concurrent.futures.ThreadPoolExecutor
- **通道通信**：queue.Queue（线程安全）
- **同步原语**：threading 模块

---

## 功能模块

### 1. 异步/等待

#### 关键字

- `异步` - 标记异步函数
- `等待` - 等待异步操作完成
- `全部` - 并发等待多个操作
- `竞速` - 竞争式等待（返回最快完成的）

#### 语法示例

```道
// 异步函数声明
异步 函数 获取数据(url)
    定义 response = 等待 网络请求(url)
    返回 response.数据

// 使用
异步 函数 主()
    定义 数据1 = 等待 获取数据("https://api.example.com/1")
    定义 数据2 = 等待 获取数据("https://api.example.com/2")
    打印(数据1, 数据2)

// 并发等待
异步 函数 获取所有数据()
    定义 结果 = 等待 全部(
        获取数据(url1),
        获取数据(url2),
        获取数据(url3),
    )
    返回 结果

// 竞速等待
异步 函数 获取最快()
    定义 结果 = 等待 竞速(
        获取数据(url1),
        获取数据(url2),
    )
    返回 结果
```

### 2. 协程和通道

#### 关键字

- `并行` - 启动协程
- `通道` - 创建通信通道
- `发送` - 发送数据到通道
- `接收` - 从通道接收数据

#### 语法示例

```道
// 无缓冲通道
定义 ch = 通道()

并行
    定义 生产者()
        遍历 i 从 1 到 10
            发送 ch, i
        发送 ch, 空  // 发送结束信号

并行
    定义 消费者()
    当 真
        定义 数据 = 接收 ch
        如果 数据 == 空
            跳出
        打印(数据)

// 缓冲通道
定义 缓冲ch = 通道(5)  // 容量为5的缓冲通道

// 遍历通道
遍历 数据 在 ch
    打印(数据)
```

### 3. 同步原语

#### 关键字和函数

- `互斥锁()` - 创建互斥锁
- `原子整数()` - 创建原子整数
- `原子布尔()` - 创建原子布尔

#### 语法示例

```道
定义 锁 = 互斥锁()
定义 计数 = 原子整数(0)

并行
    定义 任务()
    遍历 i 从 1 到 1000
        同步 锁
            计数 = 计数 + 1

// 原子操作
计数.加(1)
定义 值 = 计数.获取()
计数.设置(0)
定义 成功 = 计数.比较并设置(旧值, 新值)
```

---

## 任务分解

### 词法分析器

| 任务ID | 任务名称 | 优先级 | 预计工时 |
|--------|----------|--------|----------|
| L3.1.1 | 添加 TokenType.异步 | P0 | 2h |
| L3.1.2 | 添加 TokenType.等待 | P0 | 2h |
| L3.1.3 | 添加 TokenType.全部 | P1 | 2h |
| L3.1.4 | 添加 TokenType.竞速 | P1 | 2h |
| L3.1.5 | 添加 TokenType.并行 | P0 | 2h |
| L3.1.6 | 添加 TokenType.通道 | P0 | 2h |
| L3.1.7 | 添加 TokenType.发送 | P0 | 2h |
| L3.1.8 | 添加 TokenType.接收 | P0 | 2h |

**小计**：16小时

### 语法分析器

| 任务ID | 任务名称 | 优先级 | 预计工时 | 依赖 |
|--------|----------|--------|----------|------|
| P3.1.1 | 解析异步函数声明 | P0 | 6h | L3.1.1 |
| P3.1.2 | 解析等待表达式 | P0 | 4h | L3.1.2 |
| P3.1.3 | 解析全部调用 | P1 | 4h | L3.1.3 |
| P3.1.4 | 解析竞速调用 | P1 | 4h | L3.1.4 |
| P3.1.5 | 添加 AsyncFunctionDecl AST 节点 | P0.1 | 2h | P3.1.1 |
| P3.1.6 | 添加 AwaitExpr AST 节点 | P0.1 | 2h | P3.1.2 |
| P3.1.7 | 解析并行块 | P0 | 6h | L3.1.5 |
| P3.1.8 | 添加 CoroutineStmt AST 节点 | P0.1 | 2h | P3.1.7 |
| P3.1.9 | 解析通道创建表达式 | P0 | 4h | L3.1.6 |
| P3.1.10 | 解析发送/接收语句 | P0 | 4h | L3.1.7, L3.1.8 |

**小计**：38小时

### 解释器

#### 异步/等待

| 任务ID | 任务名称 | 优先级 | 预计工时 | 依赖 |
|--------|----------|--------|----------|------|
| I3.1.1 | 实现 DaoAsyncFunction 类 | P0 | 8h | P3.1.5 |
| I3.1.2 | 实现 AsyncContext 运行时环境 | P0 | 8h | P3.1.5 |
| I3.1.3 | 执行异步函数声明 | P0 | 6h | P3.1.5, I3.1.1 |
| I3.1.4 | 求值等待表达式 | P0 | 8h | P3.1.6, I3.1.2 |
| I3.1.5 | 实现全部并发执行 | P1 | 8h | P3.1.3, I3.1.4 |
| I3.1.6 | 实现竞速执行 | P1 | 8h | P3.1.4, I3.1.4 |
| I3.1.7 | 异步错误传播机制 | P0 | 6h | I3.1.4 |

**小计**：52小时

#### 协程和通道

| 任务ID | 任务名称 | 优先级 | 预计工时 | 依赖 |
|--------|----------|--------|----------|------|
| I3.2.1 | 实现 Channel 类（无缓冲） | P0 | 12h | P3.1.9 |
| I3.2.2 | 实现 BufferedChannel 类 | P1 | 8h | I3.2.1 |
| I3.2.3 | 实现 Coroutine 类 | P0 | 10h | P3.1.8 |
| I3.2.4 | 实现 CoroutineScheduler 调度器 | P0 | 16h | I3.2.3 |
| I3.2.5 | 执行并行块 | P0 | 10h | P3.1.8, I3.2.4 |
| I3.2.6 | 执行发送语句 | P0 | 6h | P3.1.10, I3.2.1 |
| I3.2.7 | 执行接收语句 | P0 | 6h | P3.1.10, I3.2.1 |
| I3.2.8 | 支持遍历通道语法 | P1 | 8h | I3.2.1 |

**小计**：76小时

#### 同步原语

| 任务ID | 任务名称 | 优先级 | 预计工时 | 依赖 |
|--------|----------|--------|----------|------|
| I3.3.1 | 实现 Mutex 类 | P0 | 8h | - |
| I3.3.2 | 实现 AtomicInt 类 | P0 | 8h | - |
| I3.3.3 | 实现 AtomicBool 类 | P0 | 6h | - |
| I3.3.4 | 添加互斥锁、原子操作内置函数 | P0 | 6h | I3.3.1, I3.3.2, I3.3.3 |
| I3.3.5 | 实现同步块语法 | P0 | 8h | I3.3.1 |

**小计**：36小时

### 测试

| 任务ID | 任务名称 | 优先级 | 预计工时 | 依赖 |
|--------|----------|--------|----------|------|
| T3.1 | 异步/等待测试套件 | P0 | 16h | I3.1.7 |
| T3.2 | 协程和通道测试套件 | P0 | 20h | I3.2.8 |
| T3.3 | 同步原语测试套件 | P0 | 12h | I3.3.5 |
| T3.4 | 集成测试 | P1 | 12h | T3.1, T3.2, T3.3 |

**小计**：60小时

### 示例程序

| 任务ID | 任务名称 | 优先级 | 预计工时 | 依赖 |
|--------|----------|--------|----------|•------|
| E3.1 | 异步网络请求示例 | P1 | 6h | I3.1.7 |
| E3.2 | 并行计算示例 | P1 | 6h | I3.2.5 |
| E3.3 | 生产者消费者示例 | P1 | 8h | I3.2.8 |
| E3.4 | 爬虫示例 | P1 | 10h | I3.1.7, I3.2.8 |

**小计**：30小时

### 文档

| 任务ID | 任务名称 | 优先级 | 预计工时 | 依赖 |
|--------|----------|--------|----------|------|
| D3.1 | 并发编程用户文档 | P2 | 12h | 全部实现 |
| D3.2 | API 参考文档 | P2 | 8h | 全部实现 |
| D3.3 | 最佳实践指南 | P2 | 8h | 全部实现 |

**小计**：28小时

---

## 总计

| 阶段 | 工时（小时） | 工时（工作日） |
|------|--------------|---------------|
| 词法分析器 | 16 | 2 |
| 语法分析器 | 38 | 5 |
| 解释器 | 164 | 21 |
| 测试 | 60 | 8 |
| 示例程序 | 30 | 4 |
| 文档 | 28 | 4 |
| **总计** | **336** | **44** |

---

## 技术架构

### 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                   道语言源码                        │
│                 (异步/等待/协程)                      │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                     语法分析器                       │
│          (生成异步 AST 节点)                          │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▵
┌─────────────────────────────────────────────────────────┐
│                     解释器                           │
│  ┌─────────────┬─────────────┬─────────────┐      │
│  │  Async/Wait │  Coroutines  │    Sync     │      │
│  └─────────────┴─────────────┴─────────────┘      │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                  Python 运行时                        │
│  ┌─────────────┬─────────────┬─────────────┐      │
│  │   asyncio   │  threading   │    queue    │      │
│  └─────────────┴─────────────┴─────────────┘      │
└─────────────────────────────────────────────────────────┘
```

### 核心类设计

#### 1. DaoAsyncFunction

```python
class DaoAsyncFunction(DaoFunction):
    """异步函数
    
    异步函数在调用时返回一个 asyncio.Future 而不是直接结果。
    需要通过 AsyncContext 来管理执行环境。
    """
    
    def __init__(self, name, params, body, closure_env):
        super().__init__(name, params, body, closure_env)
        self.is_async = True
    
    async def async_call(self, args, kwargs, interpreter):
        """异步调用实现
        
        使用 async/await 语法来处理嵌套的异步调用。
        """
        func_env = self.closure_env.create_child()
        
        # 绑定参数
        for param, arg in zip(self.params, args):
            func_env.define(param, arg)
        
        # 执行函数体
        return await interpreter._exec_async_block(self.body, func_env)
```

#### 2. AsyncContext

```python
class AsyncContext:
    """异步上下文
    
    管理异步执行环境，包括：
    - 当前协程
    - 事件循环
    - 任务调度
    """
    
    def __init__(self):
        self.loop = asyncio.get_event_loop()
        self.current_task = None
        self.tasks = set()
    
    async def run(self, coro):
        """运行协程"""
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        return await task
    
    def run_all(self, coros):
        """并发运行多个协程"""
        return asyncio.gather(*coros)
    
    def run_race(self, coros):
        """竞速运行，返回最快完成的"""
        return asyncio.wait(coros, return_when=asyncio.FIRST_COMPLETED)
```

#### 3. Channel

```python
class Channel:
    """无缓冲通道
    
    类似 Go 的无缓冲通道：
    - 发送者会阻塞直到有接收者
    - 接收者会阻塞直到有发送者
    """
    
    def __init__(self):
        self.queue = queue.Queue(maxsize=0)  # maxsize=0 表示无缓冲
        self.lock = threading.Lock()
        self.send_ready = threading.Condition(self.lock)
        self.recv_ready = threading.Condition(self.lock)
    
    def send(self, value):
        """发送数据（阻塞直到被接收）"""
        with self.send_ready:
            self.queue.put(value)
            self.recv_ready.notify()  # 通知接收者
            self.send_ready.wait()  # 等待接收者确认
    
    def receive(self):
        """接收数据（阻塞直到有数据）"""
        with self.recv_ready:
            while self.queue.empty():
                self.recv_ready.wait()
            value = self.queue.get()
            self.send_ready.notify()  # 通知发送者
            return value
    
    def close(self):
        """关闭通道"""
        with self.send_ready:
            self.queue.put(None)  # 发送结束信号
            self.recv_ready.notify()
```

#### 4. BufferedChannel

```python
class BufferedChannel(Channel):
    """缓冲通道
    
    有固定容量的缓冲区：
    - 缓冲区满时，发送者阻塞
    - 缓冲区空时，接收者阻塞
    """
    
    def __init__(self, capacity):
        super().__init__()
        self.queue = queue.Queue(maxsize=capacity)  # 设置缓冲容量
    
    def send(self, value):
        """发送数据（阻塞直到缓冲区有空间）"""
        self.queue.put(value)  # Queue 自动处理阻塞
    
    def receive(self):
        """接收数据（阻塞直到有数据）"""
        return self.queue.get()  # Queue 自动处理阻塞
```

#### 5. Coroutine

```python
class Coroutine:
    """协程
    
    表示一个并发执行的道语言函数。
    基于 Python threading.Thread 实现。
    """
    
    def __init__(self, func, args, kwargs, interpreter):
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.interpreter = interpreter
        self.thread = None
        self.result = None
        self.exception = None
        self.completed = threading.Event()
    
    def start(self):
        """启动协程"""
        self.thread = threading.Thread(target=self._run)
        self.thread.start()
    
    def _run(self):
        """协程执行逻辑"""
        try:
            self.result = self.func(*self.args, **self.kwargs)
        except Exception as e:
            self.exception = e
        finally:
            self.completed.set()
    
    def join(self, timeout=None):
        """等待协程完成"""
        if self.thread:
            self.thread.join(timeout=timeout)
    
    def is_done(self):
        """检查协程是否完成"""
        return self.completed.is_set()
```

#### 6. Mutex

```python
class Mutex:
    """互斥锁
    
    提供互斥访问共享资源的同步原语。
    基于 Python threading.Lock 实现。
    """
    
    def __init__(self):
        self._lock = threading.Lock()
    
    def acquire(self):
        """获取锁"""
        self._lock.acquire()
    
    def release(self):
        """释放锁"""
        self._lock.release()
    
    def __enter__(self):
        """上下文管理器入口"""
        self.acquire()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.release()
```

#### 7. AtomicInt

```python
class AtomicInt:
    """原子整数
    
    提供线程安全的整数操作。
    基于 Python threading.Lock 实现。
    """
    
    def __init__(self, value=0):
        self._value = value
        self._lock = threading.Lock()
    
    def get(self):
        """获取值"""
        with self._lock:
            return self._value
    
    def set(self, value):
        """设置值"""
        with self._lock:
            self._value = value
    
    def add(self, delta):
        """原子加法"""
        with self._lock:
            self._value += delta
            return self._value
    
    def compare_and_set(self, expected, new_value):
        """比较并设置（CAS）"""
        with self._lock:
            if self._value == expected:
                self._value = new_value
                return True
            return False
```

---

## 实现步骤

### 第一阶段：异步/等待（第1-2周）

#### 步骤 1.1：扩展词法分析器
- [ ] 添加 `异步`、`等待`、`全部`、`竞速` 关键字
- [ ] 更新 KEYWORDS 映射表
- [ ] 编写测试验证关键字识别

#### 步骤 1.2：扩展语法分析器
- [ ] 添加 `AsyncFunctionDecl` AST 节点
- [ ] 添加 `AwaitExpr` AST 节点
- [ ] 实现异步函数解析
`parse_async_function_decl()`
- [ ] 实现等待表达式解析
`parse_await_expr()`
- [ ] 实现全部/竞速调用解析

#### 步骤 1.3：实现异步函数
- [ ] 创建 `DaoAsyncFunction` 类
- [ ] 实现异步调用机制
- [ ] 创建 `AsyncContext` 运行时环境
- [ ] 实现等待表达式求值
- [ ] 实现全部并发执行
- [ ] 实现竞速执行
- [ ] 实现异步错误传播

#### 步骤 1.4：编写测试
- [ ] 测试基本异步函数
- [ ] 测试嵌套等待
- [ ] 测试全部并发等待
- [ ] 测试竞速等待
- [ ] 测试异步错误处理

#### 步骤 1.5：示例程序
- [ ] 创建异步网络请求示例
- [ ] 测试并验证

### 第二阶段：协程和通道（第3-4周）

#### 步骤 2.1：扩展词法分析器
- [ ] 添加 `并行`、`通道`、`发送`、`接收` 关键字

#### 步骤 2.2：扩展语法分析器
- [ ] 添加 `CoroutineStmt` AST 节点
- [ ] 添加 `ChannelExpr` AST 节点
- [ ] 实现并行块解析
- [ ] 实现通道创建解析
- [ ] 实现发送/接收语句解析

#### 步骤 2.3：实现通道
- [ ] 创建 `Channel` 类（无缓冲）
- [ ] 创建 `BufferedChannel` 类
- [ ] 实现发送操作（阻塞机制）
- [ ] 实现接收操作（阻塞机制）
- [ ] 实现通道关闭

#### 步骤 2.4：实现协程
- [ ] 创建 `Coroutine` 类
- [ ] 创建 `CoroutineScheduler` 调度器
- [ ] 实现协程启动和调度
- [ ] 实现并行块执行
- [ ] 实现协程同步和清理

#### 步骤 2.5：集成通道和协程
- [ ] 实现发送语句执行
- [ ] 实现接收语句执行
- [ ] 支持遍历通道语法
- [ ] 处理通道异常传播

#### 步骤 2.6：编写测试
- [ ] 测试无缓冲通道
- [ ] 测试缓冲通道
- [ ] 测试生产者消费者模式
- [ ] 测试协程调度
- [ ] 测试通道遍历

#### 步骤 2.7：示例程序
- [ ] 创建并行计算示例示例
- [ ] 创建生产者消费者示例
- [ ] 创建爬虫示例
- [ ] 测试并验证

### 第三阶段：同步原语（第5周）

#### 步骤 3.1：实现同步类
- [ ] 创建 `Mutex` 类
- [ ] 创建 `AtomicInt` 类
- [ ] 创建 `AtomicBool` 类
- [ ] 实现原子操作

#### 步骤 3.2：添加内置函数
- [ ] 添加 `互斥锁()` 内置函数
- [ ] 添加 `原子整数()` 内置函数
- [ ] 添加 `原子布尔()` 内置函数
- [ ] 注册到全局环境

#### 步骤 3.3：实现同步块语法
- [ ] 解析同步块：`同步 锁 { ... }`
- [ ] 执行同步块
- [ ] 确保锁的正确释放

#### 步骤 3.4：编写测试
- [ ] 测试互斥锁基本功能
- [ ] 测试原子整数操作
- [ ] 测试原子布尔操作
- [ ] 测试同步块

#### 步骤 3.5：综合示例
- [ ] 创建使用所有特性的综合示例
- [ ] 测试并验证

### 第四阶段：文档和优化（第6周）

#### 步骤 4.1：编写文档
- [ ] 并发编程用户指南
- [ ] API 参考文档
- [ ] 最佳实践指南

#### 步骤 4.2：性能优化
- [ ] 基准测试
- [ ] 性能分析和优化
- [ ] 内存使用优化

#### 步骤 4.3：集成测试
- [ ] 完整的集成测试套件
- [ ] 边界条件测试
- [ ] 错误恢复测试

---

## 测试计划

### 测试策略

1. **单元测试**：每个类和函数独立测试
2. **集成测试**：测试组件之间的交互
3. **并发测试**：测试并发安全性
4. **性能测试**：确保性能可接受
5. **边界测试**：测试极端情况和错误处理

### 测试覆盖目标

| 模块 | 目标覆盖率 |
|------|------------|
| 异步/等待 | ≥ 90% |
| 协程 | ≥ 85% |
| 通道 | ≥ 90% |
| 同步原语 | ≥ 95% |
| **总体** | **≥ 88%** |

### 关键测试场景

#### 异步/等待测试

```python
# test_async_await.py

def test_simple_async_function():
    """测试简单异步函数"""
    source = """
    异步 函数 hello()
        返回 "你好世界"
    
    定义 结果 = 等待 hello()
    打印(结果)
    """
    result = run(source)
    assert "你好世界" in result

def test_nested_await():
    """测试嵌套等待"""
    source = """
    异步 函数 获取数据1()
        返回 10
    
    异步 函数 获取数据2()
        定义 数据1 = 等待 获取数据1()
        返回 数据1 + 20
    
    定义 结果 = 等待 获取数据2()
    打印(结果)
    """
    result = run(source)
    assert "30" in result

def test_await_all():
    """测试全部并发等待"""
    source = """
    异步 函数 任务(id)
        返回 id * 2
    
    定义 结果 = 等待 全部(任务(1), 任务(2), 任务(3))
    打印(结果)
    """
    result = run(source)
    assert "[2, 4, 6]" in result

def test_await_race():
    """测试竞速等待"""
    source = """
    异步 函数 快任务()
        返回 "快"
    
    异步 函数 慢任务()
        等待 睡眠(1)
        返回 "慢"
    
    定义 结果 = 等待 竞速(快任务(), 慢任务())
    打印(结果)
    """
    result = run(source)
    assert "快" in result

def test_async_error_handling():
    """测试异步错误处理"""
    source = """
    异步 函数 抛错函数()
        抛出 "异步错误"
    
    尝试
        定义 结果 = 等待 抛错函数()
    捕获 err
        打印("捕获: " + err)
    """
    result = run(source)
    assert "捕获" in result
```

#### 协程和通道测试

```python
# test_coroutines.py

def test_channel_send_receive():
    """测试通道发送接收"""
    source = """
    定义 ch = 通道()
    
    并行
        定义 生产者()
            发送 ch, 42
            发送 ch, 空
    
    并行
        定义 消费者()
        定义 数据 = 接收 ch
        打印(数据)
    """
    result = run(source)
    assert "42" in result

def test_producer_consumer():
    """测试生产者消费者"""
    source = """
    定义 ch = 通道()
    
    并行
        定义 生产者()
        遍历 i 从 1 到 5
            发送 ch, i
        发送 ch, 空
    
    并行
        定义 消费者()
        当 真
            定义 数据 = 接收 ch
            如果 数据 == 空
                跳出
            打印(数据)
    """
    result = run(source)
    assert "1" in result and "5" in result

def test_buffered_channel():
    """测试缓冲通道"""
    source = """
    定义 ch = 通道(3)
    
    发送 ch, 1
    发送 ch, 2
    发送 ch, 3
    
    打印(接收 ch)
    打印(接收 ch)
    打印(接收 ch)
    """
    result = run(source)
    assert "1" in result and "2" in result and "3" in result
```

#### 同步原语测试

```python
# test_sync.py

def test_mutex():
    """测试互斥锁"""
    source = """
    定义 锁 = 互斥锁()
    定义 计数 = 0
    
    并行
        定义 任务1()
        同步 锁
            计数 = 计数 + 1
    
    并行
        定义 任务2()
        同步 锁
            计数 = 计数 + 1
    
    等待(0.1)  # 等待协程完成
    打印(计数)
    """
    result = run(source)
    assert "2" in result

def test_atomic_int():
    """测试原子整数"""
    source = """
    定义 计数 = 原子整数(0)
    
    定义 add_10()
        遍历 i 从 1 到 10
            计数.加(1)
    
    并行 add_10()
    并行 add_10()
    并行 add_10()
    
    等待(0.1)
    打印(计数.获取())
    """
    result = run(source)
    assert "30" in result
```

---

## 示例程序

### 1. 异步网络请求

**文件**：`examples/concurrency/异步网络请求.道`

```道
// 异步网络请求示例
// ================

// 模拟网络请求函数
异步 函数 网络请求(url)
    打印("请求: " + url)
    等待 睡眠(1)  // 模拟网络延迟
    返回 "来自 " + url + " 的数据"

// 获取多个URL的数据
异步 函数 获取多个数据()
    定义 urls = [
        "https://api.example.com/users",
        "https://api.example.com/posts",
        "https://api.example.com/comments",
    ]
    
    // 使用全部并发请求
    定义 结果 = 等待 全全(
        网络请求(urls[0]),
        网络请求(urls[1]),
        网络请求(urls[2]),
    )
    
    打印("所有数据获取完成!")
    遍历 数据 在 结果
        打印("  - " + 数据)

// 竞速获取最快响应
异步 函数 获取最快数据()
    定义 结果 = 等待 竞速(
        网络请求("https://fast-api.example.com"),
        网络请求("https://slow-api.example.com"),
    )
    
    打印("最快响应: " + 结果)

// 主函数
异步 函数 主()
    打印("=== 异步网络请求示例 ===")
    
    等待 获取多个数据()
    打印()
    等待 获取最快数据()

// 运行
等待 主()
```

### 2. 并行计算

**文件**：`examples/concurrency/并行计算.道`

```道
// 并行计算示例
// ============

// 计算斐波那契数列（并行版本）
函数 斐波那契(n)
    如果 n <= 1
        返回 n
    返回 斐波那契(n - 1) + 斐波那契(n - 2)

// 并行计算多个斐波那契数
定义 结果 = []
定义 锁 = 互斥锁()

函数 计算任务(n)
    定义 值 = 斐波那契(n)
    同步 锁
        结果.追加(值[0])
        结果.追加(n[1])
        结果.追加(n[2])
        结果.追加(值[3])

// 启动多个并行任务
并行 计算任务(35)
并行 计算任务(36)
并行 计算任务(37)

// 等待所有任务完成
等待(0.5)

// 排序并打印结果
排序(结果, 函数(a, b) => a[1] - b[1])
遍历 item 在 结果
    打印("斐波那契(" + item[1] + ") = " + item[0])
```

### 3. 生产者消费者

**文件**：`examples/concurrency/生产者消费者.道`

```道
// 生产者消费者模式示例
// ====================

定义 任务队列 = 通道(10)  // 缓冲通道，容量10
定义 完成信号 = 通道()

// 生产者：生成任务
定义 生产者(id)
    遍历 i 从 1 到 5
        定义 任务 = "生产者" + id + "-任务" + i
        打印("生产: " + 任务)
        发送 任务队列, 任务
        等待(0.1)
    
    发送 完成信号, 真  // 发送完成信号

// 消费者：处理任务
定义 消费者(id)
    当 真
        定义 任务 = 接收 任务队列
        打印("消费者" + id + " 处理: " + 任务)
        等待(0.2)  // 模拟处理时间

// 启动多个生产者和消费者
并行 生产者(1)
并行 生产者(2)

并行 消费者("A")
并行 消费者("B")

// 等待生产者完成
接收 完成信号
接收 完成信号

// 关闭任务队列
关闭 任务队列

打印("所有任务处理完成!")
```

### 4. 爬虫示例

**文件**：`examples/concurrency/爬虫.道`

```道
// 爬虫示例
// ==========

// 已访问的URL集合
定义 已访问 = 原子整数(0)

// URL队列
定义 url队列 = 通道(100)

// 结果列表
定义 结果 = []
定义 结果锁 = 互斥锁()

// 模拟爬取URL
异步 函数 爬取(url)
    打印("爬取: " + url)
    等待 睡眠(0.5)  // 模拟网络延迟
    
    // 解析并返回链接列表
    如果 url == "https://example.com"
        返回 [
            "https://example.com/page1",
            "https://example.com/page2",
        ]
    否则如果 url == "https://example.com/page1"
        返回 [
            "https://example.com/page3",
            "https://example.com/page4",
        ]
    否则
        返回 []

// 爬虫工作协程
定义 爬虫(id)
    当 真
        定义 url = 接收 url队列
        如果 url == 空
            跳出  // 队列关闭
        
        // 爬取URL
        定义 链接 = 等待 爬取(url)
        
        // 添加链接到结果
        同步 结果锁
            结果.追加(url)
        
        // 发现新链接
        遍历 链接 在 链接
            发送 urlqueue, 链接

// 主函数
定义 主()
    定义 种子urls = [
        "https://example.com",
    ]
    
    // 启动多个爬虫协程
    并行 爬虫("worker-1")
    并行 爬虫("worker-2")
    并行 爬虫("worker-3")
    
    // 添加种子URL
    遍历 url 在 种子urls
        发送 url队列, url
    
    // 等待一段时间后关闭
    等待(3)
    关闭 url队列
    
    // 打印结果
    打印("爬取完成!")
    打印("总共爬取: " + 长度(结果) + " 个页面")
    遍历 page 在 结果
        打印("  - " + page)

// 运行
主()
```

---

## 验收标准

### 功能完整性

- [x] **异步/等待**
  - [ ] 支持异步函数声明
  - [ ] 支持等待表达式
  - [ ] 支持全部并发等待
  - [ ] 支持竞速等待
  - [ ] 异步错误正确传播

- [x] **协程和通道**
  - [ ] 支持并行块启动协程
  - [ ] 支持无缓冲通道
  - [ ] 支持缓冲通道
  - [ ] 支持发送/接收操作
  - [ ] 支持遍历通道
  - [ ] 正确处理通道关闭

- [x] **同步原语**
  - [ ] 支持互斥锁
  - [ ] 支持原子整数操作
  - [ ] 支持原子布尔操作
  - [ ] 支持同步块语法

### 质量指标

| 指标 | 目标值 | 当前值 |
|------|--------|--------|
| 测试覆盖率 | ≥ 88% | - |
| 测试用例数 | ≥ 50 | - |
| 示例程序数 | ≥ 4 | - |
| 文档完整度 | 100% | - |

### 性能目标

| 操作 | 目标性能 |
|------|----------|
| 异步函数调用开销 | < 100ns |
| 协程启动时间 | < 1μs |
| 通道吞吐量（无缓冲） | > 50K ops/s |
| 通道吞吐量（缓冲） | > 100K ops/s |
| 互斥锁获取时间 | < 100ns |

### 安全性验证

- [ ] 无数据竞争（通过线程分析工具验证）
- [ ] 无死锁（通过超时机制检测）
- [ ] 资源正确清理（协程和通道）
- [ ] 异常正确传播（跨协程边界）

---

## 风险和挑战

### 技术挑战

1. **异步/等待集成**
   - **挑战**：将异步代码集成到同步解释器中
   - **解决方案**：使用 AsyncContext 包装器，提供桥接层

2. **通道阻塞语义**
   - **挑战**：实现 Go 风格的阻塞通道
   - **解决方案**：使用 threading.Condition 实现等待/通知机制

3. **协程同步**
   - **挑战**：协程间的正确同步和清理
   - **解决方案**：实现严格的资源生命周期管理

4. **错误传播**
   - **挑战**：跨协程边界的异常传播
   - **解决方案**：封装异常在通道消息中，或使用专用错误通道

### 性能风险

1. **协程开销**
   - **风险**：Python 线程开销较大
   - **缓解**：使用线程池，限制并发数量

2. **GIL 限制**
   - **风险**：Python GIL 限制真正的并行
   - **缓解**：使用 asyncio 进行 I/O 密集型任务

3. **内存使用**
   - **风险**：大量协程可能消耗大量内存
   - **缓解**：实现协程池，限制活跃协程数量

---

## 下一步行动

1. **立即开始第一阶段**：异步/等待功能
2. **创建开发分支**：`feature/concurrency`
3. **建立 CI/CD**：确保代码质量
4. **编写第一个测试**：测试异步函数声明
5. **逐步实现**：按照实现步骤推进

---

**文档版本**：1.0  
**创建日期**：2025年1月  
**最后更新**：2025年1月  
**维护者**：道语言开发团队