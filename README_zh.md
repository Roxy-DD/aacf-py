# AACF - 智能体编译器框架

**[English](README.md) | [中文](README_zh.md)**

一个通过装饰器、依赖分析和 DAG 调度构建 LLM 驱动的智能体管道的 Python 框架。

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![PyPI](https://img.shields.io/pypi/v/aacf.svg)](https://pypi.org/project/aacf/)
[![License](https://img.shields.io/badge/License-GPL--3.0-orange)](https://www.gnu.org/licenses/gpl-3.0.html)
[![CI](https://github.com/Roxy-DD/aacf-py/actions/workflows/ci.yml/badge.svg)](https://github.com/Roxy-DD/aacf-py/actions/workflows/ci.yml)

---

## 功能概述

使用装饰器声明 AI 节点。AACF 处理提示词构建、大模型调用、依赖分析和执行调度。

```python
from aacf import AACF, LLMConfig

app = AACF(__name__, config=LLMConfig(
    model="qwen2.5-7b-instruct",
    url="http://127.0.0.1:8080/v1/chat/completions",
))

@app.node("translate").who("Translator").what("Translate Chinese to English")
def translate(text: str):
    pass

print(translate(text="Hello World"))
# -> 你好世界
```

---

## 核心理念

**五元组 DSL。** 将提示词简化为 `who / where / what / why / how`。每个 AI 节点都是具有明确职责的原子函数。

**人类控制流程。** LLM 在节点内充当分类器，而非控制器。开发者使用原生 Python（`if/elif/for`）引导数据流。

**预编译。** 执行前，AACF 分析参数名、推断依赖、构建 DAG 并生成拓扑执行计划。

**原子执行节点。** 每个节点可独立调度、重试和缓存。失败节点按可配置的退避策略重试。

**Rust 风格错误。** `ExecutionResult` 使错误处理显式且强制。无静默失败。

**兼容 OpenAI。** 通过更改 URL 在云端 API 和本地模型之间切换。无需修改代码。

**显式代码覆盖。** 函数体为 `pass` -> 框架调用 LLM。函数体有代码 -> 你的代码执行。随时可切换回 `pass`。

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
    language="zh",  # "zh" 或 "en"
))

@app.node("title_generator").who("Title Writer").what("Generate 3 article titles for a topic").stream(True)
def title_generator(topic: str):
    pass

@app.node("article_writer").who("Article Writer").what("Write a 200-word article from a title")
def article_writer(title: str):
    pass

@app.node("content_router").who("Content Director").what("Route requests to the right node").module([title_generator, article_writer])
def content_router(user_req: str):
    pass
```

**main.py** -- 调用节点：

```python
from agents import title_generator, article_writer, content_router

# 流式输出
for chunk in title_generator(topic="AI in daily life"):
    print(chunk, end="", flush=True)

# 普通调用
print(article_writer(title="When AI learned to cook"))

# 智能路由 -- 自动分派到最佳节点
print(content_router(user_req="Write me an article about quantum computing"))
```

---

## 预编译

AACF 在执行前分析节点依赖关系：

```python
app.compile()                    # 构建 DAG 和执行计划
app.get_execution_order()        # -> ["title_generator", "article_writer", ...]
app.get_parallel_groups()        # -> [["title_generator"], ["article_writer"], ...]
app.get_dependency_graph()       # -> {"article_writer": {"title_generator"}, ...}
```

依赖推断通过匹配参数名与节点名工作。如果 `article_writer(title)` 有参数 `title` 且存在名为 `title_generator` 的节点，则当名称匹配时推断依赖。

---

## 特性

### 流式输出

```python
@app.node("writer").who("Writer").what("Write a short story").stream(True)
def writer(topic: str):
    pass

for chunk in writer(topic="Cyberpunk city"):
    print(chunk, end="", flush=True)
```

### 结构化 JSON

```python
@app.node("extractor").who("Data Extractor").what("Extract person info").format("json")
def extractor(text: str):
    pass

import json
data = json.loads(extractor(text="Li Lei, 28, engineer"))
```

### 显式代码覆盖

```python
@app.node("calculator").who("Calculator").what("Calculate result")
def calculator(expression: str):
    # 你的代码执行而非默认 LLM 调用
    return str(eval(expression))
```

### 错误处理

```python
from aacf import PipelineError

try:
    results = app.run_pipeline(inputs={...})
except PipelineError as e:
    print(f"管道失败：{e}")
```

### DAG 可视化

```python
from aacf import DAGVisualizer

visualizer = DAGVisualizer(app)
visualizer.generate_html("dag.html")  # 交互式 HTML
```

### 缓存

```python
@app.node("analyzer").who("Analyzer").what("Analyze text").cache(ttl=300)
def analyzer(text: str):
    pass
```

---

## 命令行工具

```bash
aacf init my_project        # 初始化项目
aacf run main.py            # 运行脚本
aacf sync .                 # 注入文档字符串到源码
aacf watch .                # 监听并自动注入
aacf doc aacf --port 8080   # API 文档服务器
```

---

## API 参考

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
    language="zh",
)

# 派生新配置（原配置不变）
hot_config = config(temperature=1.2)
```

---

## 项目结构

```
aacf/
  __init__.py        # 导出：AACF, LLMConfig, ExecutionResult, ...
  core.py            # 引擎：配置、HTTP 客户端、装饰器
  compiler.py        # 依赖分析、DAG、原子调度器、错误处理
  visualize.py       # 交互式 HTML DAG 可视化（pyvis）
  cli.py             # CLI 命令
  _messages.py       # 双语提示模板

examples/
  agents.py          # 演示：内容创作助手
  main.py            # 演示：调用入口
```

---

## 安装

```bash
# 从 PyPI 安装（推荐）
pip install aacf

# 从源码安装
git clone https://github.com/Roxy-DD/aacf-py.git
cd aacf-py
pip install -e .
```

Python >= 3.10。核心依赖：typer, rich。可选：pyvis（用于可视化）。

---

## 文档

详细文档请参见 [Wiki_zh.md](Wiki_zh.md)。

---

## 许可证

GPL-3.0。参见 [LICENSE](LICENSE)。
