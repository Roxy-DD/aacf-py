# AACF - 智能体编译器框架

**[English](README.md) | [中文](README_zh.md)**

一个通过装饰器、依赖分析和 DAG 调度构建 LLM 驱动的智能体管道的 Python 框架。

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![PyPI](https://img.shields.io/pypi/v/aacf.svg)](https://pypi.org/project/aacf/)
[![License](https://img.shields.io/badge/License-GPL--3.0-orange)](https://www.gnu.org/licenses/gpl-3.0.html)
[![CI](https://github.com/Roxy-DD/aacf-py/actions/workflows/ci.yml/badge.svg)](https://github.com/Roxy-DD/aacf-py/actions/workflows/ci.yml)

---

## 设计哲学与架构定位 (Macro-Micro Dual-Engine)

> **AACF 并非试图取代大模型的自发思考，而是为小模型提供一套高可用的工业级流水线。**

AACF (AI Agent Communication Framework) 的核心设计哲学基于**结构化约束**。传统的 AI 框架倾向于让模型完全自主规划与执行，而 AACF 走向了工程化的另一端：它通过强类型的五元组（`who/what/where/why/how`）与 DAG（有向无环图）将任务流固化。

基于最新的系统性客观实验研究，我们明确了该架构的最佳实践与生态位——**Macro-Micro 双引擎协同架构**：

1. **宏观层（高参数大模型，如 70B+）**：应脱离框架约束。大模型负责前沿的、多分支发散性的复杂决策与统筹，处于“自主探索”状态，并将大任务拆解为具体的线性子任务链。
2. **微观层（低参数/本地小模型，如 7B 级别，结合 AACF）**：作为下位执行引擎。当大模型拆解出线性的、重复性的信息抽取任务时，交由 AACF 框架调度小模型执行。小模型在强约束下，能够实现超越其无约束状态下的稳定产出。

这种**“大模型大脑 + 小模型流水线”**的架构，将高频、枯燥的线性任务下放，极大地节省了昂贵的大模型 Token 开销与并发限制，是通往高可用 AI 工程的最佳实践。

---

## ⚠️ 框架边界与限制 (Limitations & Warnings)

> [!WARNING]
> **切勿对高参数模型进行过度约束**
> - **能力压制**：强制高逻辑推理能力的大模型套用细粒度的 AACF 节点模板，会切断其自发组织的思维链路，产生严重的冗余和能力受限。
> - **幻觉级联（Hallucination Cascade）**：在处理多分支发散任务时，由于 AACF 的 DAG 隔离机制截断了全局上下文，一旦中间某节点发生错误（如触发 API 安全风控），下游节点由于缺乏全局视野无法纠偏，将基于局部错误信息引发严重的级联崩溃。
> - **抽象坍缩**：在使用框架分步处理分析性任务时，底层具体实体容易在节点流转和信息综合中丢失，引发高达 50% 的“实体数据丢失”。

> [!TIP]
> **推荐使用场景**
> 强烈推荐将 AACF 与本地低参数模型结合，用于**路径明确的线性任务**（如：工业化信息提取、标准数据清洗）。在此类场景下，框架不仅信息保留率高达 100%，且能发挥出极高的结构化稳定性。

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

**规则内化的自由。** 五元组 DSL（`who / where / what / why / how`）将模型思考约束在设计边界内——不是通过温度，而是通过模型内化为自身推理的显式规则。

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
aacf init my_project            # 初始化项目（创建 venv + 安装 aacf）
aacf init my_project --no-venv  # 初始化项目（跳过 venv，秒完成）
aacf run main.py                # 运行脚本
aacf sync .                     # 注入文档字符串到源码
aacf watch .                    # 监听并自动注入
aacf doc aacf --port 8080       # API 文档服务器
```

---

## MCP 服务器

AACF 提供 MCP（Model Context Protocol）服务器，用于 AI 辅助开发。AI 客户端（如 Qoder、Claude Desktop）可使用 AACF 工具来帮助你构建和管理项目。

```bash
# 安装 MCP 支持
pip install aacf[mcp]

# 启动 MCP 服务器（stdio 模式）
python -m aacf_mcp
```

### 客户端配置

Qoder（`.qoder/mcp.json`）：

```json
{
  "mcpServers": {
    "aacf": {
      "command": "python",
      "args": ["-m", "aacf_mcp"]
    }
  }
}
```

Claude Desktop（`claude_desktop_config.json`）：

```json
{
  "mcpServers": {
    "aacf": {
      "command": "python",
      "args": ["-m", "aacf_mcp"]
    }
  }
}
```

> 推荐使用 `python -m aacf_mcp` 而非 `aacf-mcp`，跨环境兼容性更好。

**可用 MCP 工具：**

| 分类 | 工具 |
|------|------|
| 项目 | `init_project`, `read_project`, `validate_project` |
| 节点 | `create_node`, `list_nodes`, `get_node_info`, `configure_node` |
| 管道 | `compile_pipeline`, `get_dependency_graph`, `get_execution_order`, `get_parallel_groups`, `run_pipeline` |

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
    api_key="",  # 可选，本地模型可省略
    temperature=0.7,
    max_tokens=1024,
    language="zh",
)

# 派生新配置（原配置不变）
hot_config = config(temperature=1.2)
```

使用 **OpenAI 兼容的 Chat Completions API**（`POST /v1/chat/completions`），支持 OpenAI、DeepSeek、Azure OpenAI、vLLM、Ollama、LM Studio、LocalAI 等。完整配置指南见 [Wiki_zh.md](Wiki_zh.md)。

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
