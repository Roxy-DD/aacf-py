# AACF Wiki / AACF 文档

> A Python framework for building LLM-driven agent pipelines through decorators, dependency analysis, and DAG-based scheduling.
> 一个通过装饰器、依赖分析和 DAG 调度构建 LLM 驱动的智能体管道的 Python 框架。

---

## Contents / 目录

1. [Architecture / 架构](#architecture--架构)
2. [Quick Start / 快速开始](#quick-start--快速开始)
3. [Core Concepts / 核心概念](#core-concepts--核心概念)
4. [Compiler / 编译器](#compiler--编译器)
5. [Error Handling / 错误处理](#error-handling--错误处理)
6. [Caching / 缓存](#caching--缓存)
7. [Visualization / 可视化](#visualization--可视化)
8. [API Reference / API 参考](#api-reference--api-参考)
9. [Advanced Usage / 高级用法](#advanced-usage--高级用法)
10. [CLI Tools / CLI 工具](#cli-tools--cli-工具)
11. [i18n / 国际化](#i18n--国际化)
12. [Project Structure / 项目结构](#project-structure--项目结构)
13. [Design Decisions / 设计决策](#design-decisions--设计决策)
14. [Troubleshooting / 故障排除](#troubleshooting--故障排除)

---

## Architecture / 架构

```
User Code / 用户代码
  agents.py          main.py          cli.py
  @app.node()        Call nodes       Commands
  @app.node()        调用节点          命令
      |                 |                |
      +-----------------+----------------+
                        |
                        v
              AACF Framework / AACF 框架
  +--------------------------------------------------+
  | core.py                                           |
  |   LLMConfig        - configuration / 配置          |
  |   llm_call()       - HTTP client + retry          |
  |                      HTTP 客户端 + 重试              |
  |   @app.node()      - decorator + prompt           |
  |                      装饰器 + 提示词                 |
  |   _inject_docstrings() - IDE support              |
  |                          IDE 支持                   |
  +--------------------------------------------------+
  | compiler.py                                       |
  |   DependencyAnalyzer - DAG construction / DAG 构建 |
  |   ExecutionPlanner   - topological order / 拓扑排序 |
  |   AtomicNode         - retry + cache              |
  |                        重试 + 缓存                  |
  |   AtomicScheduler    - dependency scheduling       |
  |                        依赖调度                     |
  |   ExecutionResult    - Rust-style result           |
  |                        Rust 风格结果                 |
  |   DAGCache           - incremental cache           |
  |                        增量缓存                     |
  +--------------------------------------------------+
  | visualize.py                                      |
  |   DAGVisualizer      - interactive HTML / 交互式可视化 |
  +--------------------------------------------------+
  | _messages.py - bilingual prompt templates / 双语提示模板 |
  +--------------------------------------------------+
                        |
                        v
            OpenAI-Compatible LLM API
            兼容 OpenAI 的大模型 API
```

### Runtime Flow / 运行时流程

1. **Define / 定义** -- User decorates function with `@app.node(who, what, ...)` / 用户使用 `@app.node(who, what, ...)` 装饰函数
2. **Register / 注册** -- Metadata stored; node registered with compiler for dependency tracking / 元数据存储；节点注册到编译器进行依赖追踪
3. **Compile / 编译** (optional / 可选) -- `app.compile()` builds DAG and execution plan / 构建 DAG 和执行计划
4. **Invoke / 调用** -- Calling the function triggers the wrapper / 调用函数触发包装器
5. **Prompt / 构建提示词** -- Decorator params -> bilingual system prompt / 装饰器参数 -> 双语系统提示词
6. **LLM call / 大模型调用** -- HTTP request to configured endpoint / 向配置的端点发送 HTTP 请求
7. **Return / 返回** -- Stream or text returned to caller / 流式或文本结果返回给调用者
8. **Inject / 注入** (atexit) -- Docstrings written back to source for IDE support / 文档字符串写回源码以支持 IDE

---

## Quick Start / 快速开始

```bash
pip install -e .
```

**agents.py** -- Define nodes / 定义节点:

```python
from aacf import AACF, LLMConfig

app = AACF(__name__, config=LLMConfig(
    model="qwen2.5-7b-instruct",
    url="http://127.0.0.1:8080/v1/chat/completions",
))

@app.node(who="Translator", what="Translate Chinese to English")
def translate(text: str):
    pass
```

**main.py** -- Call them / 调用节点:

```python
from agents import translate

print(translate(text="Hello World"))
# -> 你好世界
```

---

## Core Concepts / 核心概念

### Application Instance / 应用实例

```python
app = AACF(__name__, config=LLMConfig(
    model="qwen2.5-7b-instruct",
    url="http://localhost:8080/v1/chat/completions",
))
```

| Parameter / 参数 | Description / 描述 |
|-----------|-------------|
| `name` | App name, use `__name__` / 应用名称，使用 `__name__` |
| `config` | Global LLM config; nodes inherit automatically / 全局 LLM 配置；节点自动继承 |

### `@app.node()` Decorator / 装饰器

Transforms a function into an LLM-driven node.
将函数转换为 LLM 驱动的节点。

- Body is `pass` -> framework builds prompt, calls LLM, returns result / 函数体为 `pass` -> 框架构建提示词、调用 LLM、返回结果
- Body has code -> user code runs; decorator config preserved but unused (explicit override) / 函数体有代码 -> 用户代码执行；装饰器配置保留但不使用（显式代码覆盖）

```python
@app.node(who="Role", what="Task")
def my_agent(input_text: str):
    pass
```

Parameter names and values become the LLM's user input automatically.
参数名和值自动成为 LLM 的用户输入。

### Five-Tuple DSL / 五元组 DSL

Each node is declared with up to five fields:
每个节点通过最多五个字段声明：

| Field / 字段 | Purpose / 用途 |
|-------|---------|
| `who` | Agent role (e.g., "Translator") / 智能体角色（如 "Translator"） |
| `where` | Business context / 业务上下文 |
| `what` | Core task / 核心任务 |
| `why` | Execution intent / 执行意图 |
| `how` | Steps or constraints / 步骤或约束 |

This forces atomic thinking about each node's responsibility.
这强制了对每个节点职责的原子化思考。

### Explicit Code Override / 显式代码覆盖

```python
@app.node(who="Analyzer", what="Analyze text")
def analyzer(text: str):
    from aacf.core import llm_call
    return llm_call(
        system_prompt=f"Analyze: {text}",
        user_prompt=text,
        temperature=0.3,
    )
```

Change body back to `pass` to restore default behavior.
将函数体改回 `pass` 即可恢复默认行为。

---

## Compiler / 编译器

AACF includes a compiler layer that analyzes node dependencies before execution.
AACF 包含一个编译器层，在执行前分析节点依赖关系。

### Dependency Analysis / 依赖分析

The `DependencyAnalyzer` infers relationships between nodes by matching parameter names to node names:
`DependencyAnalyzer` 通过匹配参数名与节点名来推断节点间的关系：

```python
@app.node(who="Extractor", what="Extract data")
def extractor(text: str):
    pass

@app.node(who="Summarizer", what="Summarize data")
def summarizer(extractor: str):  # param name matches node name -> dependency / 参数名匹配节点名 -> 依赖
    pass
```

Here `summarizer` depends on `extractor` because its parameter `extractor` matches the node name.
这里 `summarizer` 依赖 `extractor`，因为其参数 `extractor` 匹配了节点名。

### Precompilation / 预编译

```python
planner = app.compile()

app.get_execution_order()    # ["extractor", "summarizer"]
app.get_parallel_groups()    # [["extractor"], ["summarizer"]]
app.get_dependency_graph()   # {"summarizer": {"extractor"}, "extractor": set()}
```

`compile()` runs Kahn's algorithm for topological sorting. Raises `CircularDependencyError` on circular dependencies, with the cycle path included in the error message.
`compile()` 运行 Kahn 算法进行拓扑排序。循环依赖时抛出 `CircularDependencyError`，错误消息中包含循环路径。

### Node Status / 节点状态

Each node has a lifecycle status:
每个节点有一个生命周期状态：

| Status / 状态 | Meaning / 含义 |
|--------|---------|
| `PENDING` | Not yet executed / 尚未执行 |
| `RUNNING` | Currently executing / 正在执行 |
| `DONE` | Completed successfully / 成功完成 |
| `FAILED` | Execution failed / 执行失败 |
| `SKIPPED` | Skipped by user or scheduler / 被用户或调度器跳过 |

### Atomic Nodes / 原子节点

`AtomicNode` wraps each user node as an independently schedulable unit with:
`AtomicNode` 将每个用户节点包装为可独立调度的单元，支持：

- Configurable retry (`max_retries`, `retry_delay`) / 可配置重试（`max_retries`、`retry_delay`）
- Result caching (`cache_enabled`, `cache_ttl`) / 结果缓存（`cache_enabled`、`cache_ttl`）
- Execution timeout / 执行超时
- Status tracking / 状态追踪

`AtomicNode.execute()` returns an `ExecutionResult` (Rust-style), not raw values or exceptions:
`AtomicNode.execute()` 返回 `ExecutionResult`（Rust 风格），而非原始值或异常：

```python
from aacf import AtomicNodeConfig
from aacf.compiler import AtomicNode

node = AtomicNode("my_node", func=my_func,
                  config=AtomicNodeConfig(max_retries=3, cache_enabled=True))
result = node.execute(input_data={"text": "hello"})

if result.is_ok():
    value = result.unwrap()      # Get the value / 获取值
elif result.is_err():
    error = result.error_info()  # Get error details / 获取错误详情
```

### AtomicScheduler / 原子调度器

`AtomicScheduler` executes multiple atomic nodes in dependency order:
`AtomicScheduler` 按依赖顺序执行多个原子节点：

```python
from aacf.compiler import AtomicScheduler, AtomicNodeConfig

scheduler = AtomicScheduler()
scheduler.add_node("extractor", extractor_func)
scheduler.add_node("summarizer", summarizer_func, dependencies={"extractor"})
results = scheduler.run_all({"extractor": {"text": "..."}})
```

Nodes whose dependencies are not yet satisfied wait. Failed nodes block downstream execution and raise `PipelineError`.
依赖未满足的节点等待。失败节点阻塞下游执行并抛出 `PipelineError`。

---

## Error Handling / 错误处理

AACF follows Rust's error philosophy: errors are explicit, typed, and carry context.
AACF 遵循 Rust 的错误哲学：错误是显式的、有类型的、携带上下文的。

### Error Hierarchy / 错误层次结构

```
AACFError                          # Base error / 基础错误
├── CircularDependencyError        # Cycle in DAG / DAG 中的循环
│   └── .cycle: List[str]          # Node names forming the cycle / 构成循环的节点名
├── DependencyError                # Missing or unresolvable dependency / 缺失或无法解析的依赖
├── NodeExecutionError             # Node failed after all retries / 节点所有重试后失败
│   ├── .node_name: str            # Failed node / 失败节点
│   ├── .attempts: int             # Number of attempts / 尝试次数
│   └── .cause: str                # Original error / 原始错误
├── NodeConfigError                # Invalid node configuration / 无效节点配置
└── PipelineError                  # Pipeline-level failure / 管道级失败
```

### ExecutionResult / 执行结果

Instead of throwing exceptions, `AtomicNode.execute()` returns `ExecutionResult`:
`AtomicNode.execute()` 不抛出异常，而是返回 `ExecutionResult`：

```python
result = node.execute(input_data)

# Check status / 检查状态
result.is_ok()          # True if succeeded / 成功则为 True
result.is_err()         # True if failed / 失败则为 True

# Get value / 获取值
result.unwrap()         # Returns value or raises NodeExecutionError / 返回值或抛出异常
result.unwrap_or(default)  # Returns value or default / 返回值或默认值

# Get error info / 获取错误信息
result.error_info()     # {"node_name": ..., "error": ..., "attempts": ..., "ok": ...}

# Transform value / 转换值 (Rust-style map / Rust 风格 map)
mapped = result.map(lambda x: x.upper())

# Metadata / 元数据
result.node_name        # Executed node name / 执行的节点名
result.attempts         # Number of attempts / 尝试次数
result.from_cache       # Whether from cache / 是否来自缓存
```

### Usage in Pipeline / 在管道中的使用

`AtomicScheduler.run_all()` handles `ExecutionResult` internally and returns a plain dict of results. It raises `PipelineError` when a node fails and blocks downstream execution.
`AtomicScheduler.run_all()` 内部处理 `ExecutionResult`，返回普通结果字典。当节点失败并阻塞下游执行时抛出 `PipelineError`。

```python
try:
    results = scheduler.run_all(inputs)
except PipelineError as e:
    print(f"Pipeline failed / 管道失败: {e}")
```

---

## Caching / 缓存

### DAG Hash Detection / DAG 哈希检测

AACF computes a SHA-256 hash of the DAG structure to detect changes:
AACF 计算 DAG 结构的 SHA-256 哈希来检测变更：

```python
analyzer = DependencyAnalyzer()
# ... register nodes ...
analyzer.analyze()

dag_hash = analyzer.compute_dag_hash()  # SHA-256 hex digest / SHA-256 十六进制摘要
```

The hash changes when:
哈希在以下情况会变化：

- Nodes are added or removed / 节点被添加或删除
- Dependencies change / 依赖关系变化
- Parameter names change / 参数名变化

### DAGCache / DAG 缓存

`DAGCache` provides incremental caching with LRU eviction:
`DAGCache` 提供带 LRU 淘汰的增量缓存：

```python
from aacf import DAGCache

cache = DAGCache(max_cache_size=100)

# Detect changes / 检测变更
changed = cache.detect_changes(analyzer, dag_id="my_pipeline")

# Store results / 存储结果
cache.set(dag_hash, {"node_a": result_a, "node_b": result_b})

# Retrieve / 获取
if cache.has_valid_cache(dag_hash):
    results = cache.get(dag_hash)

# Statistics / 统计
stats = cache.get_cache_stats()
# {"cache_size": 2, "max_cache_size": 100, "cache_keys": [...]}
```

### Node-Level Cache / 节点级缓存

Each `AtomicNode` supports per-node caching with TTL:
每个 `AtomicNode` 支持带 TTL 的节点级缓存：

```python
from aacf import AtomicNodeConfig
from aacf.compiler import AtomicNode

node = AtomicNode("my_node", func=my_func,
                  config=AtomicNodeConfig(
                      cache_enabled=True,   # Enable cache / 启用缓存
                      cache_ttl=300,        # 5 minutes / 5 分钟
                  ))

result1 = node.execute()         # Computes and caches / 计算并缓存
result2 = node.execute()         # Cache hit / 缓存命中
result3 = node.execute(force=True)  # Force recompute / 强制重新计算
```

---

## Visualization / 可视化

`DAGVisualizer` generates interactive HTML visualizations of DAG structure using pyvis.
`DAGVisualizer` 使用 pyvis 生成 DAG 结构的交互式 HTML 可视化。

```python
from aacf import AACF, DAGVisualizer

app = AACF(__name__)
# ... define nodes ...
app.compile()
results = app.run_pipeline(inputs={...})

# Generate HTML file / 生成 HTML 文件
visualizer = DAGVisualizer(app)
visualizer.generate_html("dag.html")

# Or get HTML string / 或获取 HTML 字符串
html_content = visualizer.generate_html_string()
```

### Features / 功能

- Color-coded nodes by execution status (PENDING=orange, RUNNING=blue, DONE=green, FAILED=red, SKIPPED=gray) / 按执行状态颜色编码节点（PENDING=橙色, RUNNING=蓝色, DONE=绿色, FAILED=红色, SKIPPED=灰色）
- Dependency edges with directional arrows / 带方向箭头的依赖边
- Tooltips showing node metadata (who/what/where) and execution results / 显示节点元数据（who/what/where）和执行结果的工具提示
- Interactive: drag nodes, zoom, pan / 交互式：拖拽节点、缩放、平移
- Physics-based layout / 基于物理的布局

### Customization / 自定义

```python
visualizer = DAGVisualizer(
    app,
    title="My Pipeline",       # HTML title / HTML 标题
    show_status=True,           # Color by status / 按状态着色
    show_results=True,          # Show results in tooltips / 在工具提示中显示结果
    show_dependencies=True,     # Show edges / 显示边
    width="100%",               # Width / 宽度
    height="800px",             # Height / 高度
    directed=True,              # Directed edges / 有向边
)
```

### Requirements / 依赖

```bash
pip install pyvis>=0.3.2
```

`DAGVisualizer` is imported conditionally -- if pyvis is not installed, `DAGVisualizer` will be `None`.
`DAGVisualizer` 是条件导入的 -- 如果 pyvis 未安装，`DAGVisualizer` 将为 `None`。

---

## API Reference / API 参考

### Exports / 导出

```python
from aacf import (
    AACF, LLMConfig,              # Core / 核心
    NodeStatus, AtomicNodeConfig,  # Node types / 节点类型
    ExecutionResult,               # Rust-style result / Rust 风格结果
    AACFError,                     # Base error / 基础错误
    CircularDependencyError,       # Circular dependency / 循环依赖
    NodeExecutionError,            # Node execution failure / 节点执行失败
    PipelineError,                 # Pipeline failure / 管道失败
    DAGCache,                      # Incremental cache / 增量缓存
    DAGVisualizer,                 # HTML visualization / HTML 可视化
)
```

### `@app.node()` Parameters / 参数

| Parameter / 参数 | Type / 类型 | Required / 必填 | Description / 描述 |
|-----------|------|----------|-------------|
| `who` | `str` | Yes / 是 | Agent role / 智能体角色 |
| `what` | `str` | Yes / 是 | Core task / 核心任务 |
| `where` | `str` | | Business context / 业务上下文 |
| `why` | `str` | | Execution intent / 执行意图 |
| `how` | `str \| list` | | Steps or constraints / 步骤或约束 |
| `module` | `list[Callable]` | | Sub-nodes for smart routing / 智能路由子节点 |
| `out` | `str` | | Output format requirements / 输出格式要求 |
| `stream` | `bool` | | `True` returns `Generator` / `True` 返回生成器 |
| `format` | `str` | | `"json"` enables JSON mode / `"json"` 启用 JSON 模式 |
| `branches` | `dict[str, Callable]` | | Conditional branch targets / 条件分支目标 |
| `cache_enabled` | `bool` | | Enable result caching (default `False`) / 启用结果缓存（默认 `False`） |
| `cache_ttl` | `int` | | Cache TTL in seconds (default `0`) / 缓存 TTL 秒数（默认 `0`） |
| `max_retries` | `int` | | Max retry attempts (default `3`) / 最大重试次数（默认 `3`） |
| `retry_delay` | `float` | | Delay between retries in seconds (default `1.0`) / 重试间隔秒数（默认 `1.0`） |
| `timeout` | `int` | | Execution timeout in seconds (default `0`, no timeout) / 执行超时秒数（默认 `0`，无超时） |

### `LLMConfig`

```python
config = LLMConfig(
    model="qwen2.5-7b-instruct",
    url="http://localhost:8080/v1/chat/completions",
    temperature=0.7,
    max_tokens=1024,
    stream=False,
    json_mode=False,
    language="zh",
)

hot_config = config(temperature=1.2)  # derive; original unchanged / 派生；原配置不变
```

| Method / 方法 | Description / 描述 |
|--------|-------------|
| `__call__(**kwargs)` | Create derived config copy / 创建派生配置副本 |
| `get_dict()` | Get config as dict / 获取配置字典 |
| `get_language()` | Get prompt language / 获取提示词语言 |

### `llm_call()`

```python
def llm_call(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    stream: bool = False,
    json_mode: bool = False,
    llm_config=None,
) -> Union[str, Generator[str, None, None]]:
```

HTTP request to OpenAI-compatible API. Exponential backoff retry (3 attempts). Returns `str` or `Generator`.
向兼容 OpenAI 的 API 发送 HTTP 请求。指数退避重试（3 次）。返回 `str` 或 `Generator`。

| Parameter / 参数 | Type / 类型 | Default / 默认 | Description / 描述 |
|-----------|------|---------|-------------|
| `system_prompt` | `str` | -- | System prompt / 系统提示词 |
| `user_prompt` | `str` | -- | User input / 用户输入 |
| `temperature` | `float` | `0.7` | Sampling temperature / 采样温度 |
| `stream` | `bool` | `False` | Streaming output / 流式输出 |
| `json_mode` | `bool` | `False` | JSON output / JSON 输出 |
| `llm_config` | `LLMConfig \| dict` | `None` | Config override / 配置覆盖 |

---

## Advanced Usage / 高级用法

### Streaming / 流式输出

```python
@app.node(who="Writer", what="Write a short story", stream=True)
def writer(topic: str):
    pass

for chunk in writer(topic="Cyberpunk city"):
    print(chunk, end="", flush=True)
```

### Structured JSON / 结构化 JSON

```python
@app.node(who="Extractor", what="Extract person info", format="json")
def extractor(text: str):
    pass

import json
data = json.loads(extractor(text="Li Lei, 28, engineer"))
```

### Smart Routing / 智能路由

```python
@app.node(who="Router", what="Route requests", module=[writer, extractor])
def router(user_req: str):
    pass

router(user_req="Write me a poem")  # auto-dispatches to writer / 自动分派到 writer
```

### Conditional Branching / 条件分支

```python
@app.node(who="Branch A", what="Handle type A")
def branch_a(text: str):
    return f"A: {text}"

@app.node(who="Branch B", what="Handle type B")
def branch_b(text: str):
    return f"B: {text}"

@app.node(who="Router", what="Route by type", branches={"a": branch_a, "b": branch_b})
def router(text: str):
    return "a"  # Return branch key / 返回分支键
```

### Per-Call Config Override / 单次调用配置覆盖

```python
result = writer(
    topic="AI",
    llm_config=LLMConfig(model="gpt-4", url="https://api.openai.com/v1/chat/completions")
)
```

### Custom Output Format / 自定义输出格式

```python
@app.node(
    who="Summarizer",
    what="Summarize text",
    out="Use bullet points, max 5 items, each under 20 words"
)
def summarizer(text: str):
    pass
```

### Pipeline Execution / 管道执行

```python
app = AACF(__name__)

@app.node(who="A", what="First step")
def step_a(text: str):
    return f"processed_{text}"

@app.node(who="B", what="Second step")
def step_b(step_a: str):
    return f"final_{step_a}"

# Run the full pipeline / 运行完整管道
results = app.run_pipeline(inputs={"step_a": {"text": "input"}})
# results = {"step_a": "processed_input", "step_b": "final_processed_input"}
```

---

## CLI Tools / CLI 工具

| Command / 命令 | Description / 描述 |
|---------|-------------|
| `aacf init <name>` | Initialize project / 初始化项目 |
| `aacf run <script>` | Run script / 运行脚本 |
| `aacf sync <path>` | Inject docstrings into source / 注入文档字符串到源码 |
| `aacf watch <path>` | Watch and auto-inject / 监听并自动注入 |
| `aacf doc <module>` | API doc server / API 文档服务器 |

---

## i18n / 国际化

Bilingual (Chinese/English) prompts and docstrings.
双语（中文/英文）提示词和文档字符串。

```python
app = AACF(__name__, config=LLMConfig(language="zh"))  # Chinese (default) / 中文（默认）
app = AACF(__name__, config=LLMConfig(language="en"))  # English / 英文
```

Templates centralized in `aacf/_messages.py`:
模板集中在 `aacf/_messages.py` 中：

- `PROMPT_TEMPLATES` -- system prompt construction / 系统提示词构建
- `DOCSTRING_TEMPLATES` -- docstring injection / 文档字符串注入
- `CLI_MESSAGES` -- CLI output / CLI 输出

To add a language: add a key to all three dicts, then set `language="xx"` in config.
添加语言：在三个字典中添加键，然后在配置中设置 `language="xx"`。

---

## Project Structure / 项目结构

### User Project / 用户项目

```
my_project/
  agents.py          # App instance + AI nodes / 应用实例 + AI 节点
  main.py            # Entry point / 入口文件
  pyproject.toml     # Dependency: aacf / 依赖：aacf
```

### Framework / 框架

```
aacf/
  __init__.py        # Exports: AACF, LLMConfig, ExecutionResult, ... / 导出
  core.py            # Engine: config, HTTP, decorator, docstring injection / 引擎
  compiler.py        # Dependency analysis, DAG, atomic scheduler, error handling, caching / 编译器
  visualize.py       # Interactive HTML DAG visualization (pyvis) / 交互式可视化
  cli.py             # CLI commands / CLI 命令
  _messages.py       # Bilingual prompt templates / 双语提示模板
  py.typed           # PEP 561 type marker / PEP 561 类型标记
```

### Tests / 测试

```
tests/
  test_compiler.py   # DependencyAnalyzer, ExecutionPlanner, AtomicNode, AtomicScheduler / 编译器测试
  test_config.py     # LLMConfig / 配置测试
  test_decorator.py  # @app.node(), compile, pipeline / 装饰器测试
  test_errors.py     # Error hierarchy, ExecutionResult / 错误处理测试
  test_cache.py      # DAG hash, DAGCache, TTL / 缓存测试
  test_visualize.py  # DAGVisualizer / 可视化测试
```

### Examples / 示例

```
examples/
  agents.py          # Demo: content creation assistant / 演示：内容创作助手
  main.py            # Demo: invocation entry point / 演示：调用入口
```

---

## Design Decisions / 设计决策

**Why Flask-style? / 为什么用 Flask 风格？** Python developers know the `app` + decorator pattern. One instance, one decorator.
Python 开发者熟悉 `app` + 装饰器模式。一个实例，一个装饰器。

**Why minimal dependencies? / 为什么最小化依赖？** Works in any environment. Framework stays small. Direct HTTP avoids abstraction layers. pyvis is optional (visualization only).
适用于任何环境。框架保持轻量。直接 HTTP 避免抽象层。pyvis 是可选的（仅用于可视化）。

**Why auto-inject docstrings? / 为什么自动注入文档字符串？** IDEs show accurate docstrings and type hints. The `atexit` hook keeps them current.
IDE 显示准确的文档字符串和类型提示。`atexit` 钩子保持其更新。

**Why explicit code override? / 为什么用显式代码覆盖？** Users customize prompts without forking. Start with `pass`, add code when needed, revert anytime.
用户无需 fork 即可自定义提示词。从 `pass` 开始，需要时添加代码，随时可恢复。

**Why five-tuple DSL? / 为什么用五元组 DSL？** Forces atomic thinking about each node. Reduces prompt engineering to structured declarations.
强制对每个节点进行原子化思考。将提示词工程简化为结构化声明。

**Why precompilation? / 为什么用预编译？** Dependency analysis before execution enables topological ordering, parallel grouping, and early cycle detection.
执行前的依赖分析支持拓扑排序、并行分组和早期循环检测。

**Why Rust-style errors? / 为什么用 Rust 风格错误？** `ExecutionResult` makes error handling explicit and mandatory. Callers must handle success/failure, preventing silent failures.
`ExecutionResult` 使错误处理显式且强制。调用者必须处理成功/失败，防止静默失败。

---

## Troubleshooting / 故障排除

**ModuleNotFoundError: No module named 'aacf'**

```bash
pip install -e .
```

**Connection refused / 连接被拒绝**

- Verify LLM service is running at configured URL / 确认 LLM 服务在配置的 URL 上运行
- Check firewall/proxy settings / 检查防火墙/代理设置
- Test with `curl http://127.0.0.1:8080/v1/chat/completions`

**Docstrings not appearing / 文档字符串未出现**

```bash
aacf sync .
# or / 或
aacf watch .
```

**Streaming not working / 流式输出不工作**

- Ensure `stream=True` in `@app.node()` / 确保 `@app.node()` 中 `stream=True`
- Verify LLM API supports SSE / 确认 LLM API 支持 SSE
- Check response format matches OpenAI spec / 检查响应格式是否符合 OpenAI 规范

**pyvis not installed / pyvis 未安装**

```bash
pip install pyvis>=0.3.2
```

| Error / 错误 | Cause / 原因 | Solution / 解决方案 |
|-------|-------|----------|
| `LLM Client Error: Connection refused` | LLM not running / LLM 未运行 | Start service or update URL / 启动服务或更新 URL |
| `Unrecognized response format` | API mismatch / API 不匹配 | Check API compatibility / 检查 API 兼容性 |
| `CircularDependencyError` | Cycle in node graph / 节点图中有循环 | Break the dependency cycle / 打破依赖循环 |
| `PipelineError` | Node failed, downstream blocked / 节点失败，下游阻塞 | Check failed node's error info / 检查失败节点的错误信息 |
| `NodeExecutionError` | All retries exhausted / 所有重试耗尽 | Increase `max_retries` or fix root cause / 增加 `max_retries` 或修复根本原因 |

---

## License / 许可证

GPL-3.0. See [LICENSE](LICENSE).
GPL-3.0。参见 [LICENSE](LICENSE)。
