# AACF / AACF 智能体编译器框架

Agentic AI Compiler Framework — A Python framework for building LLM-driven agent pipelines through decorators, dependency analysis, and DAG-based scheduling.

智能体编译器框架 — 一个通过装饰器、依赖分析和 DAG 调度构建 LLM 驱动的智能体管道的 Python 框架。

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-GPL--3.0-orange)](https://www.gnu.org/licenses/gpl-3.0.html)

---

## What It Does / 功能概述

You declare AI nodes with a decorator. AACF handles prompt construction, LLM calls, dependency analysis, and execution scheduling.

使用装饰器声明 AI 节点。AACF 处理提示词构建、大模型调用、依赖分析和执行调度。

```python
from aacf import AACF, LLMConfig

app = AACF(__name__, config=LLMConfig(
    model="qwen2.5-7b-instruct",
    url="http://127.0.0.1:8080/v1/chat/completions",
))

@app.node(who="Translator", what="Translate Chinese to English")
def translate(text: str):
    pass

print(translate(text="Hello World"))
# -> 你好世界
```

---

## Core Ideas / 核心理念

**Five-tuple DSL / 五元组 DSL.** Reduce prompts to `who / where / what / why / how`. Each AI node is an atomic function with a clear role.
将提示词简化为 `who / where / what / why / how`。每个 AI 节点都是具有明确职责的原子函数。

**Human-controlled flow / 人类控制流程.** LLMs act as classifiers within nodes, not as controllers. Developers use native Python (`if/elif/for`) to direct data flow.
LLM 在节点内充当分类器，而非控制器。开发者使用原生 Python（`if/elif/for`）引导数据流。

**Precompilation / 预编译.** Before execution, AACF analyzes parameter names, infers dependencies, builds a DAG, and generates a topological execution plan.
执行前，AACF 分析参数名、推断依赖、构建 DAG 并生成拓扑执行计划。

**Atomic execution nodes / 原子执行节点.** Each node is independently schedulable, retryable, and cacheable. Failed nodes retry with configurable backoff.
每个节点可独立调度、重试和缓存。失败节点按可配置的退避策略重试。

**Rust-style errors / Rust 风格错误.** `ExecutionResult` makes error handling explicit and mandatory. No silent failures.
`ExecutionResult` 使错误处理显式且强制。无静默失败。

**OpenAI-compatible / 兼容 OpenAI.** Switch between cloud APIs and local models by changing a URL. No code changes.
通过更改 URL 在云端 API 和本地模型之间切换。无需修改代码。

**Explicit code override / 显式代码覆盖.** Function body is `pass` -> framework calls LLM. Function body has code -> your code runs. Switch back to `pass` anytime.
函数体为 `pass` -> 框架调用 LLM。函数体有代码 -> 你的代码执行。随时可切换回 `pass`。

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
    language="zh",  # "zh" or "en" / "zh" 或 "en"
))

@app.node(who="Title Writer", what="Generate 3 article titles for a topic", stream=True)
def title_generator(topic: str):
    pass

@app.node(who="Article Writer", what="Write a 200-word article from a title")
def article_writer(title: str):
    pass

@app.node(who="Content Director", what="Route requests to the right node",
          module=[title_generator, article_writer])
def content_router(user_req: str):
    pass
```

**main.py** -- Call them / 调用节点:

```python
from agents import title_generator, article_writer, content_router

# Streaming / 流式输出
for chunk in title_generator(topic="AI in daily life"):
    print(chunk, end="", flush=True)

# Regular call / 普通调用
print(article_writer(title="When AI learned to cook"))

# Smart routing -- auto-dispatches to the best node / 智能路由 -- 自动分派到最佳节点
print(content_router(user_req="Write me an article about quantum computing"))
```

---

## Precompilation / 预编译

AACF analyzes node dependencies before execution:
AACF 在执行前分析节点依赖关系：

```python
app.compile()                    # Build DAG and execution plan / 构建 DAG 和执行计划
app.get_execution_order()        # -> ["title_generator", "article_writer", ...]
app.get_parallel_groups()        # -> [["title_generator"], ["article_writer"], ...]
app.get_dependency_graph()       # -> {"article_writer": {"title_generator"}, ...}
```

Dependency inference works by matching parameter names to node names. If `article_writer(title)` has a parameter `title` and there is a node called `title_generator`, the dependency is inferred when names align.

依赖推断通过匹配参数名与节点名工作。如果 `article_writer(title)` 有参数 `title` 且存在名为 `title_generator` 的节点，则当名称匹配时推断依赖。

---

## Features / 特性

### Streaming Output / 流式输出

```python
@app.node(who="Writer", what="Write a short story", stream=True)
def writer(topic: str):
    pass

for chunk in writer(topic="Cyberpunk city"):
    print(chunk, end="", flush=True)
```

### Structured JSON / 结构化 JSON

```python
@app.node(who="Data Extractor", what="Extract person info", format="json")
def extractor(text: str):
    pass

import json
data = json.loads(extractor(text="Li Lei, 28, engineer"))
```

### Explicit Code Override / 显式代码覆盖

```python
@app.node(who="Calculator", what="Calculate result")
def calculator(expression: str):
    # Your code runs instead of the default LLM call / 你的代码执行而非默认 LLM 调用
    return str(eval(expression))
```

### Error Handling / 错误处理

```python
from aacf import PipelineError

try:
    results = app.run_pipeline(inputs={...})
except PipelineError as e:
    print(f"Pipeline failed / 管道失败: {e}")
```

### DAG Visualization / DAG 可视化

```python
from aacf import DAGVisualizer

visualizer = DAGVisualizer(app)
visualizer.generate_html("dag.html")  # Interactive HTML / 交互式 HTML
```

### Caching / 缓存

```python
@app.node(who="Analyzer", what="Analyze text", cache_enabled=True, cache_ttl=300)
def analyzer(text: str):
    pass
```

---

## CLI / 命令行工具

```bash
aacf init my_project        # Initialize project / 初始化项目
aacf run main.py            # Run script / 运行脚本
aacf sync .                 # Inject docstrings into source / 注入文档字符串到源码
aacf watch .                # Watch and auto-inject / 监听并自动注入
aacf doc aacf --port 8080   # API doc server / API 文档服务器
```

---

## API Reference / API 参考

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
    language="zh",
)

# Derive new config (original unchanged) / 派生新配置（原配置不变）
hot_config = config(temperature=1.2)
```

---

## Project Structure / 项目结构

```
aacf/
  __init__.py        # Exports: AACF, LLMConfig, ExecutionResult, ... / 导出
  core.py            # Engine: config, HTTP client, decorator / 引擎
  compiler.py        # Dependency analysis, DAG, atomic scheduler, error handling / 编译器
  visualize.py       # Interactive HTML DAG visualization (pyvis) / 交互式可视化
  cli.py             # CLI commands / CLI 命令
  _messages.py       # Bilingual prompt templates / 双语提示模板

examples/
  agents.py          # Demo: content creation assistant / 演示：内容创作助手
  main.py            # Demo: invocation entry point / 演示：调用入口
```

---

## Installation / 安装

```bash
git clone https://github.com/yourusername/aacf.git
cd aacf
pip install -e .
```

Python >= 3.10. Core dependencies: typer, rich. Optional: pyvis (for visualization).
Python >= 3.10。核心依赖：typer, rich。可选：pyvis（用于可视化）。

---

## Documentation / 文档

For detailed documentation, see [Wiki.md](Wiki.md).
详细文档请参见 [Wiki.md](Wiki.md)。

---

## License / 许可证

GPL-3.0. See [LICENSE](LICENSE).
GPL-3.0。参见 [LICENSE](LICENSE)。
