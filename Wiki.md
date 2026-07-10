# AACF Wiki

**[English](Wiki.md) | [中文](Wiki_zh.md)**

> A Python framework for building LLM-driven agent pipelines through decorators, dependency analysis, and DAG-based scheduling.

---

## Contents

1. [Architecture](#architecture)
2. [Quick Start](#quick-start)
3. [Core Concepts](#core-concepts)
4. [Compiler](#compiler)
5. [Error Handling](#error-handling)
6. [Caching](#caching)
7. [Visualization](#visualization)
8. [API Reference](#api-reference)
9. [Advanced Usage](#advanced-usage)
10. [CLI Tools](#cli-tools)
11. [MCP Server](#mcp-server)
12. [i18n](#i18n)
13. [Project Structure](#project-structure)
14. [Design Decisions](#design-decisions)
15. [Troubleshooting](#troubleshooting)

---

## Architecture

```
User Code
  agents.py          main.py          cli.py
  @app.node()        Call nodes       Commands
      |                 |                |
      +-----------------+----------------+
                        |
                        v
              AACF Framework
  +--------------------------------------------------+
  | core.py                                           |
  |   LLMConfig        - configuration               |
  |   llm_call()       - HTTP client + retry         |
  |   @app.node()      - decorator + prompt          |
  |   _inject_docstrings() - IDE support             |
  +--------------------------------------------------+
  | compiler.py                                       |
  |   DependencyAnalyzer - DAG construction          |
  |   ExecutionPlanner   - topological order         |
  |   AtomicNode         - retry + cache             |
  |   AtomicScheduler    - dependency scheduling     |
  |   ExecutionResult    - Rust-style result         |
  |   DAGCache           - incremental cache         |
  +--------------------------------------------------+
  | visualize.py                                      |
  |   DAGVisualizer      - interactive HTML          |
  +--------------------------------------------------+
  | _messages.py - bilingual prompt templates        |
  +--------------------------------------------------+
                        |
                        v
            OpenAI-Compatible LLM API
```

### Runtime Flow

1. **Define** -- User defines node with chainable API `app.node("name").who("Role").what("Task").build()`
2. **Register** -- Metadata stored; node registered with compiler for dependency tracking
3. **Compile** (optional) -- `app.compile()` builds DAG and execution plan
4. **Invoke** -- Calling the function triggers the wrapper
5. **Prompt** -- Decorator params -> bilingual system prompt
6. **LLM call** -- HTTP request to configured endpoint
7. **Return** -- Stream or text returned to caller
8. **Inject** (atexit) -- Docstrings written back to source for IDE support

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
))

@app.node("translator").who("Translator").what("Translate Chinese to English").build()
def translate(text: str):
    pass
```

**main.py** -- Call them:

```python
from agents import translate

print(translate(text="Hello World"))
# -> 你好世界
```

---

## Core Concepts

### Application Instance

```python
app = AACF(__name__, config=LLMConfig(
    model="qwen2.5-7b-instruct",
    url="http://localhost:8080/v1/chat/completions",
))
```

| Parameter | Description |
|-----------|-------------|
| `name` | App name, use `__name__` |
| `config` | Global LLM config; nodes inherit automatically |

### `app.node()` Chainable API

Transforms a function into an LLM-driven node via `NodeBuilder`.

- Body is `pass` -> framework builds prompt, calls LLM, returns result
- Body has code -> user code runs; decorator config preserved but unused (explicit override)

```python
@app.node("my_agent").who("Role").what("Task").build()
def my_agent(input_text: str):
    pass
```

**Usage patterns**:

```python
# Pattern 1: Decorator with chainable config
@app.node("translator").who("Translator").what("Translate text").build()
def translator(text: str):
    pass

# Pattern 2: Separate builder and build
builder = app.node("translator").who("Translator").what("Translate text")
translator = builder.build()

# Pattern 3: Dynamic configuration
builder = app.node("translator").who("Translator").what("Translate text")
if need_cache:
    builder = builder.cache(enabled=True, ttl=300)
translator = builder.build()
```

Parameter names and values become the LLM's user input automatically.

### Five-Tuple DSL

Each node is declared with up to five fields:

| Field | Purpose |
|-------|---------|
| `who` | Agent role (e.g., "Translator") |
| `where` | Business context |
| `what` | Core task |
| `why` | Execution intent |
| `how` | Steps or constraints |

This forces atomic thinking about each node's responsibility.

### Explicit Code Override

```python
@app.node("analyzer").who("Analyzer").what("Analyze text")
def analyzer(text: str):
    from aacf.core import llm_call
    return llm_call(
        system_prompt=f"Analyze: {text}",
        user_prompt=text,
        temperature=0.3,
    )
```

Change body back to `pass` to restore default behavior.

---

## Compiler

AACF includes a compiler layer that analyzes node dependencies before execution.

### Dependency Analysis

The `DependencyAnalyzer` infers relationships between nodes by matching parameter names to node names:

```python
@app.node(who="Extractor", what="Extract data")
def extractor(text: str):
    pass

@app.node(who="Summarizer", what="Summarize data")
def summarizer(extractor: str):  # param name matches node name -> dependency
    pass
```

Here `summarizer` depends on `extractor` because its parameter `extractor` matches the node name.

### Precompilation

```python
planner = app.compile()

app.get_execution_order()    # ["extractor", "summarizer"]
app.get_parallel_groups()    # [["extractor"], ["summarizer"]]
app.get_dependency_graph()   # {"summarizer": {"extractor"}, "extractor": set()}
```

`compile()` runs Kahn's algorithm for topological sorting. Raises `CircularDependencyError` on circular dependencies, with the cycle path included in the error message.

### Node Status

Each node has a lifecycle status:

| Status | Meaning |
|--------|---------|
| `PENDING` | Not yet executed |
| `RUNNING` | Currently executing |
| `DONE` | Completed successfully |
| `FAILED` | Execution failed |
| `SKIPPED` | Skipped by user or scheduler |

### Atomic Nodes

`AtomicNode` wraps each user node as an independently schedulable unit with:

- Configurable retry (`max_retries`, `retry_delay`)
- Result caching (`cache_enabled`, `cache_ttl`)
- Execution timeout
- Status tracking

`AtomicNode.execute()` returns an `ExecutionResult` (Rust-style), not raw values or exceptions:

```python
from aacf import AtomicNodeConfig
from aacf.compiler import AtomicNode

node = AtomicNode("my_node", func=my_func,
                  config=AtomicNodeConfig(max_retries=3, cache_enabled=True))
result = node.execute(input_data={"text": "hello"})

if result.is_ok():
    value = result.unwrap()      # Get the value
elif result.is_err():
    error = result.error_info()  # Get error details
```

### AtomicScheduler

`AtomicScheduler` executes multiple atomic nodes in dependency order:

```python
from aacf.compiler import AtomicScheduler, AtomicNodeConfig

scheduler = AtomicScheduler()
scheduler.add_node("extractor", extractor_func)
scheduler.add_node("summarizer", summarizer_func, dependencies={"extractor"})
results = scheduler.run_all({"extractor": {"text": "..."}})
```

Nodes whose dependencies are not yet satisfied wait. Failed nodes block downstream execution and raise `PipelineError`.

---

## Error Handling

AACF follows Rust's error philosophy: errors are explicit, typed, and carry context.

### Error Hierarchy

```
AACFError                          # Base error
├── CircularDependencyError        # Cycle in DAG
│   └── .cycle: List[str]          # Node names forming the cycle
├── DependencyError                # Missing or unresolvable dependency
├── NodeExecutionError             # Node failed after all retries
│   ├── .node_name: str            # Failed node
│   ├── .attempts: int             # Number of attempts
│   └── .cause: str                # Original error
├── NodeConfigError                # Invalid node configuration
└── PipelineError                  # Pipeline-level failure
```

### ExecutionResult

Instead of throwing exceptions, `AtomicNode.execute()` returns `ExecutionResult`:

```python
result = node.execute(input_data)

# Check status
result.is_ok()          # True if succeeded
result.is_err()         # True if failed

# Get value
result.unwrap()         # Returns value or raises NodeExecutionError
result.unwrap_or(default)  # Returns value or default

# Get error info
result.error_info()     # {"node_name": ..., "error": ..., "attempts": ..., "ok": ...}

# Transform value (Rust-style map)
mapped = result.map(lambda x: x.upper())

# Metadata
result.node_name        # Executed node name
result.attempts         # Number of attempts
result.from_cache       # Whether from cache
```

### Usage in Pipeline

`AtomicScheduler.run_all()` handles `ExecutionResult` internally and returns a plain dict of results. It raises `PipelineError` when a node fails and blocks downstream execution.

```python
try:
    results = scheduler.run_all(inputs)
except PipelineError as e:
    print(f"Pipeline failed: {e}")
```

---

## Caching

### DAG Hash Detection

AACF computes a SHA-256 hash of the DAG structure to detect changes:

```python
analyzer = DependencyAnalyzer()
# ... register nodes ...
analyzer.analyze()

dag_hash = analyzer.compute_dag_hash()  # SHA-256 hex digest
```

The hash changes when:

- Nodes are added or removed
- Dependencies change
- Parameter names change

### DAGCache

`DAGCache` provides incremental caching with LRU eviction:

```python
from aacf import DAGCache

cache = DAGCache(max_cache_size=100)

# Detect changes
changed = cache.detect_changes(analyzer, dag_id="my_pipeline")

# Store results
cache.set(dag_hash, {"node_a": result_a, "node_b": result_b})

# Retrieve
if cache.has_valid_cache(dag_hash):
    results = cache.get(dag_hash)

# Statistics
stats = cache.get_cache_stats()
# {"cache_size": 2, "max_cache_size": 100, "cache_keys": [...]}
```

### Node-Level Cache

Each `AtomicNode` supports per-node caching with TTL:

```python
from aacf import AtomicNodeConfig
from aacf.compiler import AtomicNode

node = AtomicNode("my_node", func=my_func,
                  config=AtomicNodeConfig(
                      cache_enabled=True,   # Enable cache
                      cache_ttl=300,        # 5 minutes
                  ))

result1 = node.execute()         # Computes and caches
result2 = node.execute()         # Cache hit
result3 = node.execute(force=True)  # Force recompute
```

---

## Visualization

`DAGVisualizer` generates interactive HTML visualizations of DAG structure using pyvis.

```python
from aacf import AACF, DAGVisualizer

app = AACF(__name__)
# ... define nodes ...
app.compile()
results = app.run_pipeline(inputs={...})

# Generate HTML file
visualizer = DAGVisualizer(app)
visualizer.generate_html("dag.html")

# Or get HTML string
html_content = visualizer.generate_html_string()
```

### Features

- Color-coded nodes by execution status (PENDING=orange, RUNNING=blue, DONE=green, FAILED=red, SKIPPED=gray)
- Dependency edges with directional arrows
- Tooltips showing node metadata (who/what/where) and execution results
- Interactive: drag nodes, zoom, pan
- Physics-based layout

### Customization

```python
visualizer = DAGVisualizer(
    app,
    title="My Pipeline",       # HTML title
    show_status=True,           # Color by status
    show_results=True,          # Show results in tooltips
    show_dependencies=True,     # Show edges
    width="100%",               # Width
    height="800px",             # Height
    directed=True,              # Directed edges
)
```

### Requirements

```bash
pip install pyvis>=0.3.2
```

`DAGVisualizer` is imported conditionally -- if pyvis is not installed, `DAGVisualizer` will be `None`.

---

## API Reference

### Exports

```python
from aacf import (
    AACF, LLMConfig,              # Core
    NodeStatus, AtomicNodeConfig,  # Node types
    ExecutionResult,               # Rust-style result
    AACFError,                     # Base error
    CircularDependencyError,       # Circular dependency
    NodeExecutionError,            # Node execution failure
    PipelineError,                 # Pipeline failure
    DAGCache,                      # Incremental cache
    DAGVisualizer,                 # HTML visualization
)
```

### `@app.node()` Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `who` | `str` | Yes | Agent role |
| `what` | `str` | Yes | Core task |
| `where` | `str` | | Business context |
| `why` | `str` | | Execution intent |
| `how` | `str \| list` | | Steps or constraints |
| `module` | `list[Callable]` | | Sub-nodes for smart routing |
| `out` | `str` | | Output format requirements |
| `stream` | `bool` | | `True` returns `Generator` |
| `format` | `str` | | `"json"` enables JSON mode |
| `branches` | `dict[str, Callable]` | | Conditional branch targets |
| `cache_enabled` | `bool` | | Enable result caching (default `False`) |
| `cache_ttl` | `int` | | Cache TTL in seconds (default `0`) |
| `max_retries` | `int` | | Max retry attempts (default `3`) |
| `retry_delay` | `float` | | Delay between retries in seconds (default `1.0`) |
| `timeout` | `int` | | Execution timeout in seconds (default `0`, no timeout) |

### `LLMConfig`

```python
config = LLMConfig(
    model="qwen2.5-7b-instruct",
    url="http://localhost:8080/v1/chat/completions",
    temperature=0.7,
    max_tokens=1024,
    stream=False,
    json_mode=False,
    language="en",
)

hot_config = config(temperature=1.2)  # derive; original unchanged
```

| Method | Description |
|--------|-------------|
| `__call__(**kwargs)` | Create derived config copy |
| `get_dict()` | Get config as dict |
| `get_language()` | Get prompt language |

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

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `system_prompt` | `str` | -- | System prompt |
| `user_prompt` | `str` | -- | User input |
| `temperature` | `float` | `0.7` | Sampling temperature |
| `stream` | `bool` | `False` | Streaming output |
| `json_mode` | `bool` | `False` | JSON output |
| `llm_config` | `LLMConfig \| dict` | `None` | Config override |

---

## Advanced Usage

### Streaming

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

### Smart Routing

```python
@app.node("router").who("Router").what("Route requests").module([writer, extractor])
def router(user_req: str):
    pass

router(user_req="Write me a poem")  # auto-dispatches to writer
```

### Conditional Branching

```python
@app.node("branch_a").who("Branch A").what("Handle type A")
def branch_a(text: str):
    return f"A: {text}"

@app.node("branch_b").who("Branch B").what("Handle type B")
def branch_b(text: str):
    return f"B: {text}"

@app.node("router").who("Router").what("Route by type")
def router(text: str):
    return "a"  # Return branch key
```

### Per-Call Config Override

```python
result = writer(
    topic="AI",
    llm_config=LLMConfig(model="gpt-4", url="https://api.openai.com/v1/chat/completions")
)
```

### Custom Output Format

```python
@app.node("summarizer").who("Summarizer").what("Summarize text").out("Use bullet points, max 5 items, each under 20 words")
def summarizer(text: str):
    pass
```

### Pipeline Execution

```python
app = AACF(__name__)

@app.node("step_a").who("A").what("First step")
def step_a(text: str):
    return f"processed_{text}"

@app.node("step_b").who("B").what("Second step")
def step_b(step_a: str):
    return f"final_{step_a}"

# Run the full pipeline
results = app.run_pipeline(inputs={"step_a": {"text": "input"}})
# results = {"step_a": "processed_input", "step_b": "final_processed_input"}
```

---

## CLI Tools

| Command | Description |
|---------|-------------|
| `aacf init <name>` | Initialize project (creates venv + installs aacf) |
| `aacf init <name> --no-venv` | Initialize project (skip venv, instant) |
| `aacf run <script>` | Run script |
| `aacf sync <path>` | Inject docstrings into source |
| `aacf watch <path>` | Watch and auto-inject |
| `aacf doc <module>` | API doc server |

---

## MCP Server

AACF provides an MCP (Model Context Protocol) server for AI-assisted development. AI clients like Claude Desktop can use AACF tools to help build and manage projects.

### Installation

```bash
pip install aacf[mcp]
```

### Usage

```bash
# Start MCP server (stdio mode)
aacf-mcp

# Or run as Python module
python -m aacf_mcp
```

### Client Configuration

Qoder (`.qoder/mcp.json`):

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

Claude Desktop (`claude_desktop_config.json`):

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

> Use `python -m aacf_mcp` instead of `aacf-mcp` for better compatibility across environments.
```

### Available Tools

| Category | Tool | Description |
|----------|------|-------------|
| **Project** | `init_project` | Initialize new AACF project |
| | `read_project` | Read project structure/files |
| | `validate_project` | Validate project configuration |
| **Nodes** | `create_node` | Create new node in agents.py |
| | `list_nodes` | List all nodes in project |
| | `get_node_info` | Get detailed node info |
| | `configure_node` | Modify node configuration |
| **Pipeline** | `compile_pipeline` | Compile and analyze dependencies |
| | `get_dependency_graph` | Get DAG dependency graph |
| | `get_execution_order` | Get topological execution order |
| | `get_parallel_groups` | Get parallel execution groups |
| | `run_pipeline` | Execute pipeline with inputs |

### Architecture

The MCP server uses `FastMCP` (high-level Python SDK) with stdio transport. All tools operate by reading/writing Python files in AACF projects, without modifying the core AACF runtime. This ensures clean separation between the AI assistance layer and the framework itself.

Source code in `aacf_mcp/`:

```
aacf_mcp/
  __init__.py        # Exports: create_server
  server.py          # FastMCP server + main entry
  tools/
    nodes.py         # Node management tools (4)
    pipeline.py      # Pipeline analysis tools (5)
    project.py       # Project management tools (3)
```

---

## CI/CD

### Automated Testing

Every push to `master` and every pull request triggers the CI workflow:

- **Lint** -- `ruff check` + `ruff format --check`
- **Test** -- `pytest` across Python 3.10, 3.11, 3.12, 3.13 with coverage
- **Build** -- `python -m build` to verify package builds correctly

### Automated Release

Creating a GitHub Release triggers automatic publishing to PyPI via OIDC Trusted Publisher (no API tokens needed):

1. Update version in `pyproject.toml`
2. Create and push a tag: `git tag -a v<version> -m "Release v<version>"`
3. Create a GitHub Release: `gh release create v<version> --title "..." --notes "..."`
4. GitHub Actions builds and publishes to PyPI automatically

---

## i18n

Bilingual (Chinese/English) prompts and docstrings.

```python
app = AACF(__name__, config=LLMConfig(language="en"))  # English
app = AACF(__name__, config=LLMConfig(language="zh"))  # Chinese (default)
```

Templates centralized in `aacf/_messages.py`:

- `PROMPT_TEMPLATES` -- system prompt construction
- `DOCSTRING_TEMPLATES` -- docstring injection
- `CLI_MESSAGES` -- CLI output

To add a language: add a key to all three dicts, then set `language="xx"` in config.

---

## Project Structure

### User Project

```
my_project/
  agents.py          # App instance + AI nodes
  main.py            # Entry point
  pyproject.toml     # Dependency: aacf
```

### Framework

```
aacf/
  __init__.py        # Exports: AACF, LLMConfig, ExecutionResult, ...
  core.py            # Engine: config, HTTP, decorator, docstring injection
  compiler.py        # Dependency analysis, DAG, atomic scheduler, error handling, caching
  visualize.py       # Interactive HTML DAG visualization (pyvis)
  cli.py             # CLI commands
  _messages.py       # Bilingual prompt templates
  py.typed           # PEP 561 type marker
```

### MCP (Optional)

```
aacf_mcp/
  __init__.py        # Exports: create_server
  server.py          # FastMCP server with stdio transport
  tools/
    nodes.py         # Node management tools
    pipeline.py      # Pipeline analysis tools
    project.py       # Project management tools
```

### Tests

```
tests/
  test_compiler.py   # DependencyAnalyzer, ExecutionPlanner, AtomicNode, AtomicScheduler
  test_config.py     # LLMConfig
  test_decorator.py  # @app.node(), compile, pipeline
  test_errors.py     # Error hierarchy, ExecutionResult
  test_cache.py      # DAG hash, DAGCache, TTL
  test_visualize.py  # DAGVisualizer
```

### Examples

```
examples/
  agents.py          # Demo: content creation assistant
  main.py            # Demo: invocation entry point
```

---

## Design Decisions

**Why Flask-style?** Python developers know the `app` + decorator pattern. One instance, one decorator.

**Why minimal dependencies?** Works in any environment. Framework stays small. Direct HTTP avoids abstraction layers. pyvis is optional (visualization only).

**Why auto-inject docstrings?** IDEs show accurate docstrings and type hints. The `atexit` hook keeps them current.

**Why explicit code override?** Users customize prompts without forking. Start with `pass`, add code when needed, revert anytime.

**Why five-tuple DSL?** Forces atomic thinking about each node. Reduces prompt engineering to structured declarations.

**Why precompilation?** Dependency analysis before execution enables topological ordering, parallel grouping, and early cycle detection.

**Why Rust-style errors?** `ExecutionResult` makes error handling explicit and mandatory. Callers must handle success/failure, preventing silent failures.

---

## Troubleshooting

**ModuleNotFoundError: No module named 'aacf'**

```bash
pip install aacf
```

**Connection refused**

- Verify LLM service is running at configured URL
- Check firewall/proxy settings
- Test with `curl http://127.0.0.1:8080/v1/chat/completions`

**Docstrings not appearing**

```bash
aacf sync .
# or
aacf watch .
```

**Streaming not working**

- Ensure `stream=True` in `@app.node()`
- Verify LLM API supports SSE
- Check response format matches OpenAI spec

**pyvis not installed**

```bash
pip install pyvis>=0.3.2
```

| Error | Cause | Solution |
|-------|-------|----------|
| `LLM Client Error: Connection refused` | LLM not running | Start service or update URL |
| `Unrecognized response format` | API mismatch | Check API compatibility |
| `CircularDependencyError` | Cycle in node graph | Break the dependency cycle |
| `PipelineError` | Node failed, downstream blocked | Check failed node's error info |
| `NodeExecutionError` | All retries exhausted | Increase `max_retries` or fix root cause |
| MCP server not starting | `aacf-mcp` not in PATH | Use `python -m aacf_mcp` in mcp.json config |
| `aacf init` slow | venv creation + pip install | Use `--no-venv` flag for instant init |

---

## License

GPL-3.0. See [LICENSE](LICENSE).
