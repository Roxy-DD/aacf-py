# AACF 文档

**[English](Wiki.md) | [中文](Wiki_zh.md)**

> 一个通过装饰器、依赖分析和 DAG 调度构建 LLM 驱动的智能体管道的 Python 框架。

---

## 目录

1. [架构](#架构)
2. [快速开始](#快速开始)
3. [核心概念](#核心概念)
4. [编译器](#编译器)
5. [错误处理](#错误处理)
6. [缓存](#缓存)
7. [可视化](#可视化)
8. [API 参考](#api-参考)
9. [高级用法](#高级用法)
10. [CLI 工具](#cli-工具)
11. [国际化](#国际化)
12. [项目结构](#项目结构)
13. [设计决策](#设计决策)
14. [故障排除](#故障排除)

---

## 架构

```
用户代码
  agents.py          main.py          cli.py
  @app.node()        调用节点          命令
      |                 |                |
      +-----------------+----------------+
                        |
                        v
              AACF 框架
  +--------------------------------------------------+
  | core.py                                           |
  |   LLMConfig        - 配置                         |
  |   llm_call()       - HTTP 客户端 + 重试            |
  |   @app.node()      - 装饰器 + 提示词               |
  |   _inject_docstrings() - IDE 支持                  |
  +--------------------------------------------------+
  | compiler.py                                       |
  |   DependencyAnalyzer - DAG 构建                    |
  |   ExecutionPlanner   - 拓扑排序                    |
  |   AtomicNode         - 重试 + 缓存                 |
  |   AtomicScheduler    - 依赖调度                    |
  |   ExecutionResult    - Rust 风格结果               |
  |   DAGCache           - 增量缓存                    |
  +--------------------------------------------------+
  | visualize.py                                      |
  |   DAGVisualizer      - 交互式 HTML                |
  +--------------------------------------------------+
  | _messages.py - 双语提示模板                        |
  +--------------------------------------------------+
                        |
                        v
            兼容 OpenAI 的大模型 API
```

### 运行时流程

1. **定义** -- 用户使用链式 API 定义节点 `app.node("name").who("Role").what("Task").build()`
2. **注册** -- 元数据存储；节点注册到编译器进行依赖追踪
3. **编译**（可选） -- `app.compile()` 构建 DAG 和执行计划
4. **调用** -- 调用函数触发包装器
5. **构建提示词** -- 装饰器参数 -> 双语系统提示词
6. **大模型调用** -- 向配置的端点发送 HTTP 请求
7. **返回** -- 流式或文本结果返回给调用者
8. **注入**（atexit） -- 文档字符串写回源码以支持 IDE

---

## 快速开始

```bash
pip install aacf
```

**agents.py** -- 定义节点：

```python
from aacf import AACF, LLMConfig

app = AACF(__name__, config=LLMConfig(
    model="qwen2.5-7b-instruct",
    url="http://127.0.0.1:8080/v1/chat/completions",
))

@app.node("translator").who("Translator").what("Translate Chinese to English").build()
def translate(text: str):
    pass
```

**main.py** -- 调用节点：

```python
from agents import translate

print(translate(text="Hello World"))
# -> 你好世界
```

---

## 核心概念

### 应用实例

```python
app = AACF(__name__, config=LLMConfig(
    model="qwen2.5-7b-instruct",
    url="http://localhost:8080/v1/chat/completions",
))
```

| 参数 | 描述 |
|------|------|
| `name` | 应用名称，使用 `__name__` |
| `config` | 全局 LLM 配置；节点自动继承 |

### `app.node()` 链式调用 API

通过 `NodeBuilder` 将函数转换为 LLM 驱动的节点。

- 函数体为 `pass` -> 框架构建提示词、调用 LLM、返回结果
- 函数体有代码 -> 用户代码执行；装饰器配置保留但不使用（显式代码覆盖）

```python
@app.node("my_agent").who("Role").what("Task").build()
def my_agent(input_text: str):
    pass
```

**使用模式**：

```python
# 方式 1：装饰器 + 链式配置
@app.node("translator").who("Translator").what("Translate text").build()
def translator(text: str):
    pass

# 方式 2：分离构建器和构建
builder = app.node("translator").who("Translator").what("Translate text")
translator = builder.build()

# 方式 3：动态配置
builder = app.node("translator").who("Translator").what("Translate text")
if need_cache:
    builder = builder.cache(enabled=True, ttl=300)
translator = builder.build()
```

参数名和值自动成为 LLM 的用户输入。

### 五元组 DSL

每个节点通过最多五个字段声明：

| 字段 | 用途 |
|------|------|
| `who` | 智能体角色（如 "Translator"） |
| `where` | 业务上下文 |
| `what` | 核心任务 |
| `why` | 执行意图 |
| `how` | 步骤或约束 |

这强制了对每个节点职责的原子化思考。

### 显式代码覆盖

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

将函数体改回 `pass` 即可恢复默认行为。

---

## 编译器

AACF 包含一个编译器层，在执行前分析节点依赖关系。

### 依赖分析

`DependencyAnalyzer` 通过匹配参数名与节点名来推断节点间的关系：

```python
@app.node(who="Extractor", what="Extract data")
def extractor(text: str):
    pass

@app.node(who="Summarizer", what="Summarize data")
def summarizer(extractor: str):  # 参数名匹配节点名 -> 依赖
    pass
```

这里 `summarizer` 依赖 `extractor`，因为其参数 `extractor` 匹配了节点名。

### 预编译

```python
planner = app.compile()

app.get_execution_order()    # ["extractor", "summarizer"]
app.get_parallel_groups()    # [["extractor"], ["summarizer"]]
app.get_dependency_graph()   # {"summarizer": {"extractor"}, "extractor": set()}
```

`compile()` 运行 Kahn 算法进行拓扑排序。循环依赖时抛出 `CircularDependencyError`，错误消息中包含循环路径。

### 节点状态

每个节点有一个生命周期状态：

| 状态 | 含义 |
|------|------|
| `PENDING` | 尚未执行 |
| `RUNNING` | 正在执行 |
| `DONE` | 成功完成 |
| `FAILED` | 执行失败 |
| `SKIPPED` | 被用户或调度器跳过 |

### 原子节点

`AtomicNode` 将每个用户节点包装为可独立调度的单元，支持：

- 可配置重试（`max_retries`、`retry_delay`）
- 结果缓存（`cache_enabled`、`cache_ttl`）
- 执行超时
- 状态追踪

`AtomicNode.execute()` 返回 `ExecutionResult`（Rust 风格），而非原始值或异常：

```python
from aacf import AtomicNodeConfig
from aacf.compiler import AtomicNode

node = AtomicNode("my_node", func=my_func,
                  config=AtomicNodeConfig(max_retries=3, cache_enabled=True))
result = node.execute(input_data={"text": "hello"})

if result.is_ok():
    value = result.unwrap()      # 获取值
elif result.is_err():
    error = result.error_info()  # 获取错误详情
```

### 原子调度器

`AtomicScheduler` 按依赖顺序执行多个原子节点：

```python
from aacf.compiler import AtomicScheduler, AtomicNodeConfig

scheduler = AtomicScheduler()
scheduler.add_node("extractor", extractor_func)
scheduler.add_node("summarizer", summarizer_func, dependencies={"extractor"})
results = scheduler.run_all({"extractor": {"text": "..."}})
```

依赖未满足的节点等待。失败节点阻塞下游执行并抛出 `PipelineError`。

---

## 错误处理

AACF 遵循 Rust 的错误哲学：错误是显式的、有类型的、携带上下文的。

### 错误层次结构

```
AACFError                          # 基础错误
├── CircularDependencyError        # DAG 中的循环
│   └── .cycle: List[str]          # 构成循环的节点名
├── DependencyError                # 缺失或无法解析的依赖
├── NodeExecutionError             # 节点所有重试后失败
│   ├── .node_name: str            # 失败节点
│   ├── .attempts: int             # 尝试次数
│   └── .cause: str                # 原始错误
├── NodeConfigError                # 无效节点配置
└── PipelineError                  # 管道级失败
```

### ExecutionResult

`AtomicNode.execute()` 不抛出异常，而是返回 `ExecutionResult`：

```python
result = node.execute(input_data)

# 检查状态
result.is_ok()          # 成功则为 True
result.is_err()         # 失败则为 True

# 获取值
result.unwrap()         # 返回值或抛出异常
result.unwrap_or(default)  # 返回值或默认值

# 获取错误信息
result.error_info()     # {"node_name": ..., "error": ..., "attempts": ..., "ok": ...}

# 转换值（Rust 风格 map）
mapped = result.map(lambda x: x.upper())

# 元数据
result.node_name        # 执行的节点名
result.attempts         # 尝试次数
result.from_cache       # 是否来自缓存
```

### 在管道中的使用

`AtomicScheduler.run_all()` 内部处理 `ExecutionResult`，返回普通结果字典。当节点失败并阻塞下游执行时抛出 `PipelineError`。

```python
try:
    results = scheduler.run_all(inputs)
except PipelineError as e:
    print(f"管道失败：{e}")
```

---

## 缓存

### DAG 哈希检测

AACF 计算 DAG 结构的 SHA-256 哈希来检测变更：

```python
analyzer = DependencyAnalyzer()
# ... 注册节点 ...
analyzer.analyze()

dag_hash = analyzer.compute_dag_hash()  # SHA-256 十六进制摘要
```

哈希在以下情况会变化：

- 节点被添加或删除
- 依赖关系变化
- 参数名变化

### DAGCache

`DAGCache` 提供带 LRU 淘汰的增量缓存：

```python
from aacf import DAGCache

cache = DAGCache(max_cache_size=100)

# 检测变更
changed = cache.detect_changes(analyzer, dag_id="my_pipeline")

# 存储结果
cache.set(dag_hash, {"node_a": result_a, "node_b": result_b})

# 获取
if cache.has_valid_cache(dag_hash):
    results = cache.get(dag_hash)

# 统计
stats = cache.get_cache_stats()
# {"cache_size": 2, "max_cache_size": 100, "cache_keys": [...]}
```

### 节点级缓存

每个 `AtomicNode` 支持带 TTL 的节点级缓存：

```python
from aacf import AtomicNodeConfig
from aacf.compiler import AtomicNode

node = AtomicNode("my_node", func=my_func,
                  config=AtomicNodeConfig(
                      cache_enabled=True,   # 启用缓存
                      cache_ttl=300,        # 5 分钟
                  ))

result1 = node.execute()         # 计算并缓存
result2 = node.execute()         # 缓存命中
result3 = node.execute(force=True)  # 强制重新计算
```

---

## 可视化

`DAGVisualizer` 使用 pyvis 生成 DAG 结构的交互式 HTML 可视化。

```python
from aacf import AACF, DAGVisualizer

app = AACF(__name__)
# ... 定义节点 ...
app.compile()
results = app.run_pipeline(inputs={...})

# 生成 HTML 文件
visualizer = DAGVisualizer(app)
visualizer.generate_html("dag.html")

# 或获取 HTML 字符串
html_content = visualizer.generate_html_string()
```

### 功能

- 按执行状态颜色编码节点（PENDING=橙色, RUNNING=蓝色, DONE=绿色, FAILED=红色, SKIPPED=灰色）
- 带方向箭头的依赖边
- 显示节点元数据（who/what/where）和执行结果的工具提示
- 交互式：拖拽节点、缩放、平移
- 基于物理的布局

### 自定义

```python
visualizer = DAGVisualizer(
    app,
    title="My Pipeline",       # HTML 标题
    show_status=True,           # 按状态着色
    show_results=True,          # 在工具提示中显示结果
    show_dependencies=True,     # 显示边
    width="100%",               # 宽度
    height="800px",             # 高度
    directed=True,              # 有向边
)
```

### 依赖

```bash
pip install pyvis>=0.3.2
```

`DAGVisualizer` 是条件导入的 -- 如果 pyvis 未安装，`DAGVisualizer` 将为 `None`。

---

## API 参考

### 导出

```python
from aacf import (
    AACF, LLMConfig,              # 核心
    NodeStatus, AtomicNodeConfig,  # 节点类型
    ExecutionResult,               # Rust 风格结果
    AACFError,                     # 基础错误
    CircularDependencyError,       # 循环依赖
    NodeExecutionError,            # 节点执行失败
    PipelineError,                 # 管道失败
    DAGCache,                      # 增量缓存
    DAGVisualizer,                 # HTML 可视化
)
```

### `@app.node()` 参数

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `who` | `str` | 是 | 智能体角色 |
| `what` | `str` | 是 | 核心任务 |
| `where` | `str` | | 业务上下文 |
| `why` | `str` | | 执行意图 |
| `how` | `str \| list` | | 步骤或约束 |
| `module` | `list[Callable]` | | 智能路由子节点 |
| `out` | `str` | | 输出格式要求 |
| `stream` | `bool` | | `True` 返回生成器 |
| `format` | `str` | | `"json"` 启用 JSON 模式 |
| `branches` | `dict[str, Callable]` | | 条件分支目标 |
| `cache_enabled` | `bool` | | 启用结果缓存（默认 `False`） |
| `cache_ttl` | `int` | | 缓存 TTL 秒数（默认 `0`） |
| `max_retries` | `int` | | 最大重试次数（默认 `3`） |
| `retry_delay` | `float` | | 重试间隔秒数（默认 `1.0`） |
| `timeout` | `int` | | 执行超时秒数（默认 `0`，无超时） |

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

hot_config = config(temperature=1.2)  # 派生；原配置不变
```

| 方法 | 描述 |
|------|------|
| `__call__(**kwargs)` | 创建派生配置副本 |
| `get_dict()` | 获取配置字典 |
| `get_language()` | 获取提示词语言 |

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

向兼容 OpenAI 的 API 发送 HTTP 请求。指数退避重试（3 次）。返回 `str` 或 `Generator`。

| 参数 | 类型 | 默认 | 描述 |
|------|------|------|------|
| `system_prompt` | `str` | -- | 系统提示词 |
| `user_prompt` | `str` | -- | 用户输入 |
| `temperature` | `float` | `0.7` | 采样温度 |
| `stream` | `bool` | `False` | 流式输出 |
| `json_mode` | `bool` | `False` | JSON 输出 |
| `llm_config` | `LLMConfig \| dict` | `None` | 配置覆盖 |

---

## 高级用法

### 流式输出

```python
@app.node(who="Writer", what="Write a short story", stream=True)
def writer(topic: str):
    pass

for chunk in writer(topic="Cyberpunk city"):
    print(chunk, end="", flush=True)
```

### 结构化 JSON

```python
@app.node(who="Extractor", what="Extract person info", format="json")
def extractor(text: str):
    pass

import json
data = json.loads(extractor(text="Li Lei, 28, engineer"))
```

### 智能路由

```python
@app.node(who="Router", what="Route requests", module=[writer, extractor])
def router(user_req: str):
    pass

router(user_req="Write me a poem")  # 自动分派到 writer
```

### 条件分支

```python
@app.node(who="Branch A", what="Handle type A")
def branch_a(text: str):
    return f"A: {text}"

@app.node(who="Branch B", what="Handle type B")
def branch_b(text: str):
    return f"B: {text}"

@app.node(who="Router", what="Route by type", branches={"a": branch_a, "b": branch_b})
def router(text: str):
    return "a"  # 返回分支键
```

### 单次调用配置覆盖

```python
result = writer(
    topic="AI",
    llm_config=LLMConfig(model="gpt-4", url="https://api.openai.com/v1/chat/completions")
)
```

### 自定义输出格式

```python
@app.node(
    who="Summarizer",
    what="Summarize text",
    out="Use bullet points, max 5 items, each under 20 words"
)
def summarizer(text: str):
    pass
```

### 管道执行

```python
app = AACF(__name__)

@app.node(who="A", what="First step")
def step_a(text: str):
    return f"processed_{text}"

@app.node(who="B", what="Second step")
def step_b(step_a: str):
    return f"final_{step_a}"

# 运行完整管道
results = app.run_pipeline(inputs={"step_a": {"text": "input"}})
# results = {"step_a": "processed_input", "step_b": "final_processed_input"}
```

---

## CLI 工具

| 命令 | 描述 |
|------|------|
| `aacf init <name>` | 初始化项目 |
| `aacf run <script>` | 运行脚本 |
| `aacf sync <path>` | 注入文档字符串到源码 |
| `aacf watch <path>` | 监听并自动注入 |
| `aacf doc <module>` | API 文档服务器 |

---

## CI/CD

### 自动化测试

每次推送到 `master` 和每个 Pull Request 都会触发 CI 工作流：

- **Lint** -- `ruff check` + `ruff format --check`
- **Test** -- `pytest` 跨 Python 3.10、3.11、3.12、3.13 运行，带覆盖率
- **Build** -- `python -m build` 验证包构建正确

### 自动化发布

创建 GitHub Release 后通过 OIDC 可信发布商自动发布到 PyPI（无需 API Token）：

1. 更新 `pyproject.toml` 中的版本号
2. 创建并推送 tag：`git tag -a v<版本> -m "Release v<版本>"`
3. 创建 GitHub Release：`gh release create v<版本> --title "..." --notes "..."`
4. GitHub Actions 自动构建并发布到 PyPI

---

## 国际化

双语（中文/英文）提示词和文档字符串。

```python
app = AACF(__name__, config=LLMConfig(language="zh"))  # 中文（默认）
app = AACF(__name__, config=LLMConfig(language="en"))  # 英文
```

模板集中在 `aacf/_messages.py` 中：

- `PROMPT_TEMPLATES` -- 系统提示词构建
- `DOCSTRING_TEMPLATES` -- 文档字符串注入
- `CLI_MESSAGES` -- CLI 输出

添加语言：在三个字典中添加键，然后在配置中设置 `language="xx"`。

---

## 项目结构

### 用户项目

```
my_project/
  agents.py          # 应用实例 + AI 节点
  main.py            # 入口文件
  pyproject.toml     # 依赖：aacf
```

### 框架

```
aacf/
  __init__.py        # 导出：AACF, LLMConfig, ExecutionResult, ...
  core.py            # 引擎：配置、HTTP、装饰器、文档字符串注入
  compiler.py        # 依赖分析、DAG、原子调度器、错误处理、缓存
  visualize.py       # 交互式 HTML DAG 可视化（pyvis）
  cli.py             # CLI 命令
  _messages.py       # 双语提示模板
  py.typed           # PEP 561 类型标记
```

### 测试

```
tests/
  test_compiler.py   # DependencyAnalyzer, ExecutionPlanner, AtomicNode, AtomicScheduler
  test_config.py     # LLMConfig
  test_decorator.py  # @app.node(), compile, pipeline
  test_errors.py     # 错误层次结构, ExecutionResult
  test_cache.py      # DAG 哈希, DAGCache, TTL
  test_visualize.py  # DAGVisualizer
```

### 示例

```
examples/
  agents.py          # 演示：内容创作助手
  main.py            # 演示：调用入口
```

---

## 设计决策

**为什么用 Flask 风格？** Python 开发者熟悉 `app` + 装饰器模式。一个实例，一个装饰器。

**为什么最小化依赖？** 适用于任何环境。框架保持轻量。直接 HTTP 避免抽象层。pyvis 是可选的（仅用于可视化）。

**为什么自动注入文档字符串？** IDE 显示准确的文档字符串和类型提示。`atexit` 钩子保持其更新。

**为什么用显式代码覆盖？** 用户无需 fork 即可自定义提示词。从 `pass` 开始，需要时添加代码，随时可恢复。

**为什么用五元组 DSL？** 强制对每个节点进行原子化思考。将提示词工程简化为结构化声明。

**为什么用预编译？** 执行前的依赖分析支持拓扑排序、并行分组和早期循环检测。

**为什么用 Rust 风格错误？** `ExecutionResult` 使错误处理显式且强制。调用者必须处理成功/失败，防止静默失败。

---

## 故障排除

**ModuleNotFoundError: No module named 'aacf'**

```bash
pip install aacf
```

**连接被拒绝**

- 确认 LLM 服务在配置的 URL 上运行
- 检查防火墙/代理设置
- 测试 `curl http://127.0.0.1:8080/v1/chat/completions`

**文档字符串未出现**

```bash
aacf sync .
# 或
aacf watch .
```

**流式输出不工作**

- 确保 `@app.node()` 中 `stream=True`
- 确认 LLM API 支持 SSE
- 检查响应格式是否符合 OpenAI 规范

**pyvis 未安装**

```bash
pip install pyvis>=0.3.2
```

| 错误 | 原因 | 解决方案 |
|------|------|----------|
| `LLM Client Error: Connection refused` | LLM 未运行 | 启动服务或更新 URL |
| `Unrecognized response format` | API 不匹配 | 检查 API 兼容性 |
| `CircularDependencyError` | 节点图中有循环 | 打破依赖循环 |
| `PipelineError` | 节点失败，下游阻塞 | 检查失败节点的错误信息 |
| `NodeExecutionError` | 所有重试耗尽 | 增加 `max_retries` 或修复根本原因 |

---

## 许可证

GPL-3.0。参见 [LICENSE](LICENSE)。
