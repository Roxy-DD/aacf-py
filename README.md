# AACF - Agentic AI Compiler Framework

**[English](README.md) | [中文](README_zh.md)**

A Python framework for building LLM-driven agent pipelines through decorators, dependency analysis, and DAG-based scheduling.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![PyPI](https://img.shields.io/pypi/v/aacf.svg)](https://pypi.org/project/aacf/)
[![License](https://img.shields.io/badge/License-GPL--3.0-orange)](https://www.gnu.org/licenses/gpl-3.0.html)
[![CI](https://github.com/Roxy-DD/aacf-py/actions/workflows/ci.yml/badge.svg)](https://github.com/Roxy-DD/aacf-py/actions/workflows/ci.yml)

---

## What It Does

You declare AI nodes with a decorator. AACF handles prompt construction, LLM calls, dependency analysis, and execution scheduling.

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

## Core Ideas

**Five-tuple DSL.** Reduce prompts to `who / where / what / why / how`. Each AI node is an atomic function with a clear role.

**Human-controlled flow.** LLMs act as classifiers within nodes, not as controllers. Developers use native Python (`if/elif/for`) to direct data flow.

**Precompilation.** Before execution, AACF analyzes parameter names, infers dependencies, builds a DAG, and generates a topological execution plan.

**Atomic execution nodes.** Each node is independently schedulable, retryable, and cacheable. Failed nodes retry with configurable backoff.

**Rust-style errors.** `ExecutionResult` makes error handling explicit and mandatory. No silent failures.

**OpenAI-compatible.** Switch between cloud APIs and local models by changing a URL. No code changes.

**Explicit code override.** Function body is `pass` -> framework calls LLM. Function body has code -> your code runs. Switch back to `pass` anytime.

---

## Quick Start

```bash
pip install aacf
```

**agents.py** -- Define nodes:

```python
from aacf import AACF, LLMConfig

app = AACF(__name__, config=LLMConfig(
    model="qwen2.5-7b-instruct",
    url="http://127.0.0.1:8080/v1/chat/completions",
    language="en",  # "zh" or "en"
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

**main.py** -- Call them:

```python
from agents import title_generator, article_writer, content_router

# Streaming
for chunk in title_generator(topic="AI in daily life"):
    print(chunk, end="", flush=True)

# Regular call
print(article_writer(title="When AI learned to cook"))

# Smart routing -- auto-dispatches to the best node
print(content_router(user_req="Write me an article about quantum computing"))
```

---

## Precompilation

AACF analyzes node dependencies before execution:

```python
app.compile()                    # Build DAG and execution plan
app.get_execution_order()        # -> ["title_generator", "article_writer", ...]
app.get_parallel_groups()        # -> [["title_generator"], ["article_writer"], ...]
app.get_dependency_graph()       # -> {"article_writer": {"title_generator"}, ...}
```

Dependency inference works by matching parameter names to node names. If `article_writer(title)` has a parameter `title` and there is a node called `title_generator`, the dependency is inferred when names align.

---

## Features

### Streaming Output

```python
@app.node("writer").who("Writer").what("Write a short story").stream(True)
def writer(topic: str):
    pass

for chunk in writer(topic="Cyberpunk city"):
    print(chunk, end="", flush=True)
```

### Structured JSON

```python
@app.node("extractor").who("Data Extractor").what("Extract person info").format("json")
def extractor(text: str):
    pass

import json
data = json.loads(extractor(text="Li Lei, 28, engineer"))
```

### Explicit Code Override

```python
@app.node("calculator").who("Calculator").what("Calculate result")
def calculator(expression: str):
    # Your code runs instead of the default LLM call
    return str(eval(expression))
```

### Error Handling

```python
from aacf import PipelineError

try:
    results = app.run_pipeline(inputs={...})
except PipelineError as e:
    print(f"Pipeline failed: {e}")
```

### DAG Visualization

```python
from aacf import DAGVisualizer

visualizer = DAGVisualizer(app)
visualizer.generate_html("dag.html")  # Interactive HTML
```

### Caching

```python
@app.node("analyzer").who("Analyzer").what("Analyze text").cache(ttl=300)
def analyzer(text: str):
    pass
```

---

## CLI

```bash
aacf init my_project        # Initialize project
aacf run main.py            # Run script
aacf sync .                 # Inject docstrings into source
aacf watch .                # Watch and auto-inject
aacf doc aacf --port 8080   # API doc server
```

---

## MCP Server

AACF provides an MCP (Model Context Protocol) server for AI-assisted development. AI clients like Claude Desktop can use AACF tools to help you build and manage projects.

```bash
# Install with MCP support
pip install aacf[mcp]

# Start MCP server (stdio mode)
aacf-mcp
```

**Claude Desktop Configuration** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "aacf": {
      "command": "aacf-mcp"
    }
  }
}
```

**Available MCP Tools:**

| Category | Tools |
|----------|-------|
| Project | `init_project`, `read_project`, `validate_project` |
| Nodes | `create_node`, `list_nodes`, `get_node_info`, `configure_node` |
| Pipeline | `compile_pipeline`, `get_dependency_graph`, `get_execution_order`, `get_parallel_groups`, `run_pipeline` |

---

## API Reference

### `@app.node()` Chainable API

```python
# Basic usage
@app.node("name").who("Role").what("Task")
def my_node(param: str):
    pass

# Full chainable configuration
@app.node("name") \
    .who("Role") \
    .where("Context") \
    .what("Task") \
    .why("Intent") \
    .how("Steps") \
    .stream(True) \
    .format("json") \
    .cache(ttl=300) \
    .retry(max_attempts=3, delay=1.0) \
    .timeout(30)
def my_node(param: str):
    pass
```

### Chainable Methods

| Method | Description |
|--------|-------------|
| `.who(role)` | Set agent role |
| `.where(context)` | Set business context |
| `.what(task)` | Set core task |
| `.why(intent)` | Set execution intent |
| `.how(steps)` | Set steps or constraints |
| `.module([nodes])` | Set sub-nodes for smart routing |
| `.out(format)` | Set output format requirements |
| `.stream(True)` | Enable streaming output |
| `.format("json")` | Enable JSON mode |
| `.cache(ttl=300)` | Enable caching with TTL |
| `.retry(max_attempts=3, delay=1.0)` | Configure retry behavior |
| `.timeout(30)` | Set execution timeout |

### `LLMConfig`

```python
config = LLMConfig(
    model="qwen2.5-7b-instruct",
    url="http://localhost:8080/v1/chat/completions",
    temperature=0.7,
    max_tokens=1024,
    language="en",
)

# Derive new config (original unchanged)
hot_config = config(temperature=1.2)
```

---

## Project Structure

```
aacf/
  __init__.py        # Exports: AACF, LLMConfig, ExecutionResult, ...
  core.py            # Engine: config, HTTP client, decorator
  compiler.py        # Dependency analysis, DAG, atomic scheduler, error handling
  visualize.py       # Interactive HTML DAG visualization (pyvis)
  cli.py             # CLI commands
  _messages.py       # Bilingual prompt templates

aacf_mcp/            # MCP Server (optional)
  __init__.py        # Exports: create_server
  server.py          # FastMCP server with stdio transport
  tools/
    nodes.py         # Node management tools
    pipeline.py      # Pipeline analysis tools
    project.py       # Project management tools

examples/
  agents.py          # Demo: content creation assistant
  main.py            # Demo: invocation entry point
```

---

## Installation

```bash
# From PyPI (recommended)
pip install aacf

# With MCP server support
pip install aacf[mcp]

# From source
git clone https://github.com/Roxy-DD/aacf-py.git
cd aacf-py
pip install -e .
```

Python >= 3.10. Core dependencies: typer, rich. Optional: pyvis (visualization), mcp (MCP server).

---

## Documentation

For detailed documentation, see [Wiki.md](Wiki.md).

---

## License

GPL-3.0. See [LICENSE](LICENSE).
