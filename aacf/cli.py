# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 AACF Contributors
"""
AACF CLI — 命令行工具 / Command Line Interface

提供 aacf init / run / sync / watch / doc 等 CLI 子命令。
Provides CLI subcommands: init / run / sync / watch / doc.
"""

import ast
import importlib.util
import inspect
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore
    except AttributeError:
        pass
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    try:
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore
    except AttributeError:
        pass

app = typer.Typer(
    name="aacf",
    help="AACF: Agentic AI Compiler Framework CLI / 智能体编译器框架命令行工具",
    add_completion=False,
)
console = Console()


# ────────────────────────────────────────────
# Docstring 注入工具（供 sync / watch 使用）/ Docstring injection tool (for sync/watch)
# ────────────────────────────────────────────


def inject_docstrings_for_file(filepath: str) -> bool:
    """
    通过反射读取 Python 文件中的 @app.node 节点，并将 Docstring 注入到源码中。
    Read Python file via reflection to find @app.node nodes and inject docstrings into source.

    供 ``aacf sync`` 和 ``aacf watch`` 命令调用。
    Called by ``aacf sync`` and ``aacf watch`` commands.

    Args:
        filepath: 目标 Python 文件路径 / Target Python file path

    Returns:
        True 如果成功注入 / True if injection succeeded, False otherwise
    """

    def _inject_docstrings_to_py(filepath, nodes):
        """
        将 docstring 注入到单个 Python 文件中 / Inject docstrings into a single Python file.

        Args:
            filepath: 目标文件路径 / Target file path
            nodes: (函数对象, 元数据字典, 签名) 的列表 / List of (func, meta_dict, signature) tuples

        Returns:
            True 如果实际修改了文件 / True if the file was actually modified
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                source_lines = f.readlines()
            tree = ast.parse("".join(source_lines))
            docstring_ranges = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    doc = ast.get_docstring(node)
                    if doc and "AACF" in doc:
                        expr_node = node.body[0]
                        docstring_ranges[node.name] = (expr_node.lineno, expr_node.end_lineno)
        except Exception:
            return False

        funcs_to_inject = []
        for func, meta, sig in nodes:
            name = func.__name__
            # 如果源码中已有 AACF docstring，跳过（幂等性）
            # If source already has AACF docstring, skip (idempotent)
            if name in docstring_ranges:
                continue
            try:
                _, start_lineno = inspect.getsourcelines(func)
            except Exception:
                continue
            funcs_to_inject.append((start_lineno, func, meta))

        if not funcs_to_inject:
            return False

        funcs_to_inject.sort(key=lambda x: x[0], reverse=True)

        for start_lineno, func, meta in funcs_to_inject:
            name = func.__name__
            if name in docstring_ranges:
                start, end = docstring_ranges[name]
                del source_lines[start - 1 : end]

            idx = start_lineno - 1
            paren_count = 0
            in_def = False
            colon_idx = idx
            def_indent = 0
            for i in range(idx, len(source_lines)):
                line = source_lines[i]
                if not in_def and line.lstrip().startswith("def "):
                    in_def = True
                    def_indent = len(line) - len(line.lstrip())
                paren_count += line.count("(") - line.count(")")
                if in_def and paren_count == 0 and ":" in line:
                    colon_idx = i
                    break

            indent_str = " " * (def_indent + 4)
            who = meta.get("who", "未命名智能体 / AI Agent")
            what = meta.get("what", "未定义任务 / Task undefined")
            where = meta.get("where", "未知环境 / Environment unknown")

            docstring_lines = [
                f'{indent_str}"""\n',
                f"{indent_str}🤖 【AACF 智能节点 / Smart Node】: {who}\n",
                f"{indent_str}🎯 核心任务 / Core Task: {what}\n",
                f"{indent_str}📍 执行环境 / Environment: {where}\n",
                f'{indent_str}"""\n',
            ]

            line = source_lines[colon_idx]
            colon_pos = line.find(":", line.rfind(")"))
            if colon_pos != -1:
                before_colon = line[: colon_pos + 1]
                after_colon = line[colon_pos + 1 :].strip()
                source_lines[colon_idx] = before_colon + "\n"
                if after_colon:
                    docstring_lines.append(f"{indent_str}{after_colon}\n")

            source_lines = source_lines[: colon_idx + 1] + docstring_lines + source_lines[colon_idx + 1 :]

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.writelines(source_lines)
            return True
        except Exception:
            return False

    target_path = Path(filepath).resolve()
    if not target_path.exists() or target_path.suffix != ".py":
        return False

    module_name = target_path.stem
    parent_dir = str(target_path.parent)
    sys.path.insert(0, parent_dir)

    try:
        spec = importlib.util.spec_from_file_location(module_name, str(target_path))
        if spec is None or spec.loader is None:
            return False
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    except Exception as e:
        print(f"Failed to import {filepath}: {e}")
        sys.path.pop(0)
        return False

    sys.path.pop(0)

    has_nodes = False
    nodes = []
    for name, obj in inspect.getmembers(module):
        if inspect.isfunction(obj) and hasattr(obj, "__aacf_meta__"):
            # 仅处理定义在当前文件中的函数，跳过从其他文件导入的函数
            # Only process functions defined in the current file, skip imported ones
            # 使用 inspect.unwrap 追溯 @wraps 包装链，获取原始函数的源文件
            # Use inspect.unwrap to follow @wraps chain to get original function's source file
            try:
                original_func = inspect.unwrap(obj)
                func_file = inspect.getsourcefile(original_func)
                if func_file and Path(func_file).resolve() != target_path:
                    continue
            except (OSError, TypeError):
                continue
            has_nodes = True
            meta = obj.__aacf_meta__
            sig = inspect.signature(obj)
            nodes.append((obj, meta, sig))

    if not has_nodes:
        return False

    return _inject_docstrings_to_py(filepath, nodes) or False


# ────────────────────────────────────────────
# CLI Commands / 命令行命令
# ─────────────────────────────────────────────


@app.command()
def init(
    project_name: str = typer.Argument(..., help="The name of your new AACF project / 新项目名称"),
    no_venv: bool = typer.Option(False, "--no-venv", help="Skip virtual environment creation / 跳过虚拟环境创建"),
):
    """Initialize a new AACF project with the recommended directory structure.
    初始化一个新的 AACF 项目，包含推荐的目录结构。"""
    console.print(
        Panel.fit(
            f"[bold blue]Initializing AACF Project / 初始化项目:[/] [green]{project_name}[/]",
            border_style="blue",
        )
    )
    project_dir = Path.cwd() / project_name
    if project_dir.exists():
        console.print(f"[bold red]✖[/] Directory '{project_name}' already exists / 目录 '{project_name}' 已存在。")
        raise typer.Exit(code=1)

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        # Step 1: Create project files / 创建项目文件
        task = progress.add_task(description="Creating project structure / 创建项目结构...", total=None)
        # 创建项目目录 / Create project directory
        project_dir.mkdir(parents=True)

        # 创建 agents.py — 节点定义 / Create agents.py — node definitions
        agents_py = project_dir / "agents.py"
        agents_py.write_text(
            "# SPDX-License-Identifier: GPL-3.0\n"
            '"""AI agent node definitions / AI 智能体节点定义。\n'
            "\n"
            "Use the chainable API to configure nodes:\n"
            "使用链式 API 配置节点：\n"
            "\n"
            '    @app.node("name").who("role").what("task")\n'
            "    def my_node(param: str):\n"
            "        pass\n"
            "\n"
            "Available chain methods / 可用链式方法：\n"
            "    .who(role)        - Agent role / 智能体角色\n"
            "    .what(task)       - Core task / 核心任务\n"
            "    .where(context)   - Business context / 业务环境\n"
            "    .why(reason)      - Execution intent / 执行意图\n"
            "    .how(method)      - Operation method / 操作方法\n"
            "    .stream(True)     - Enable streaming / 启用流式输出\n"
            '    .format("json")   - JSON output / JSON 输出\n'
            "    .out(requirement) - Output format / 输出格式要求\n"
            "    .cache(ttl=300)   - Enable cache / 启用缓存\n"
            "    .retry(max_attempts=3, delay=1.0) - Retry config / 重试配置\n"
            "    .timeout(seconds) - Timeout config / 超时配置\n"
            '"""\n'
            "\n"
            "from aacf import AACF, LLMConfig\n"
            "\n"
            "# ── Initialize App / 初始化应用 ──────────────────────────────────────\n"
            "app = AACF(\n"
            "    __name__,\n"
            "    config=LLMConfig(\n"
            '        model="qwen2.5-7b-instruct",\n'
            '        url="http://127.0.0.1:8080/v1/chat/completions",\n'
            '        language="zh",  # "zh" (中文) or "en" (English)\n'
            "    ),\n"
            ")\n"
            "\n"
            "\n"
            "# ── Node Definitions / 节点定义 ──────────────────────────────────────\n"
            "\n"
            "\n"
            '@app.node("greeting").who("友好助手").what("向用户打招呼并回答问题")\n'
            "def greeting(name: str):\n"
            '    """A simple greeting node. / 简单的问候节点。"""\n'
            "    pass\n"
            "\n"
            "\n"
            '@app.node("summary").who("摘要专家").what("根据输入内容生成简洁摘要").cache(ttl=300)\n'
            "def summary(greeting: str):\n"
            '    """A summary node that depends on greeting (param name matches upstream node).\n'
            '    摘要节点，依赖 greeting（参数名匹配上游节点名）。"""\n'
            "    pass\n",
            encoding="utf-8",
        )

        # 创建 main.py — 入口文件 / Create main.py — entry point
        main_py = project_dir / "main.py"
        main_py.write_text(
            "# SPDX-License-Identifier: GPL-3.0\n"
            '"""Application entry point / 应用入口文件。\n'
            "\n"
            "Demonstrates:\n"
            "  1. Calling individual nodes / 调用单个节点\n"
            "  2. Pipeline execution with dependency analysis / 带依赖分析的管道执行\n"
            '"""\n'
            "\n"
            "from agents import app, greeting, summary\n"
            "\n"
            "\n"
            'if __name__ == "__main__":\n'
            "    # 1. Call a single node / 调用单个节点\n"
            '    print("=== Node Call / 节点调用 ===")\n'
            '    print(greeting(name="World"))\n'
            "    print()\n"
            "\n"
            "    # 2. Run pipeline (auto-resolves dependencies) / 运行管道（自动解析依赖）\n"
            '    print("=== Pipeline / 管道执行 ===")\n'
            '    results = app.run_pipeline(inputs={"greeting": {"name": "AACF"}})\n'
            "    for node_name, result in results.items():\n"
            '        print(f"{node_name}: {result}")\n',
            encoding="utf-8",
        )

        # 创建 README.md / Create README.md
        readme_md = project_dir / "README.md"
        readme_md.write_text(
            f"# {project_name}\n\n"
            "An AACF-powered AI agent project.\n\n"
            "## Project Structure / 项目结构\n\n"
            "```\n"
            f"{project_name}/\n"
            "├── agents.py    # Node definitions (chainable API) / 节点定义（链式 API）\n"
            "├── main.py      # Entry point / 入口文件\n"
            "├── README.md    # This file / 本文件\n"
            "└── .gitignore\n"
            "```\n\n"
            "## Quick Start / 快速开始\n\n"
            "```bash\n"
            "# Install dependencies / 安装依赖\n"
            "pip install aacf\n\n"
            "# Run the project / 运行项目\n"
            "python main.py\n"
            "```\n\n"
            "## Node Configuration / 节点配置\n\n"
            "Use the chainable API to configure nodes in `agents.py`:\n"
            "在 `agents.py` 中使用链式 API 配置节点：\n\n"
            "```python\n"
            '@app.node("name")           # Node name / 节点名称\n'
            '    .who("role")            # Agent role / 智能体角色\n'
            '    .what("task")           # Core task / 核心任务\n'
            '    .where("context")       # Business context / 业务环境\n'
            "    .stream(True)           # Streaming output / 流式输出\n"
            '    .format("json")         # JSON output / JSON 输出\n'
            "    .cache(ttl=300)         # Cache 5 min / 缓存 5 分钟\n"
            "    .retry(max_attempts=3)  # Retry config / 重试配置\n"
            "def my_node(param: str):\n"
            "    pass\n"
            "```\n\n"
            "## Pipeline / 管道执行\n\n"
            "AACF automatically analyzes dependencies between nodes and builds a DAG.\n"
            "AACF 自动分析节点间的依赖关系并构建 DAG。\n\n"
            "```python\n"
            "# Run pipeline with inputs / 运行管道并传入输入\n"
            'results = app.run_pipeline(inputs={"node_name": {"param": "value"}})\n'
            "\n"
            "# Query execution plan / 查询执行计划\n"
            "app.get_execution_order()   # Topological order / 拓扑顺序\n"
            "app.get_parallel_groups()   # Parallel groups / 并行分组\n"
            "app.get_dependency_graph()  # Dependency graph / 依赖图\n"
            "```\n\n"
            "## Dependency Convention / 依赖约定\n\n"
            "Parameter names matching upstream node names create automatic dependencies:\n"
            "参数名匹配上游节点名时，自动建立依赖关系：\n\n"
            "```python\n"
            '@app.node("extractor").who("提取器").what("提取信息")\n'
            "def extractor(text: str):\n"
            "    pass\n"
            "\n"
            '@app.node("summarizer").who("摘要器").what("生成摘要")\n'
            'def summarizer(extractor: str):  # param "extractor" -> depends on node "extractor"\n'
            '    pass                          # 参数名 "extractor" 依赖节点 "extractor"\n'
            "```\n\n"
            "## MCP Server / MCP 服务\n\n"
            "AACF provides an MCP (Model Context Protocol) server for AI-assisted development.\n"
            "AACF 提供 MCP 服务，支持 AI 辅助开发。\n\n"
            "### Configuration / 配置方式\n\n"
            "**VS Code / Cursor** — already configured in `.vscode/mcp.json`:\n"
            "```json\n"
            "{\n"
            '  "servers": {\n'
            '    "aacf": {\n'
            '      "command": "python",\n'
            '      "args": ["-m", "aacf_mcp"]\n'
            "    }\n"
            "  }\n"
            "}\n"
            "```\n\n"
            "**Qoder** — already configured in `.qoder/mcp.json`:\n"
            "```json\n"
            "{\n"
            '  "mcpServers": {\n'
            '    "aacf": {\n'
            '      "command": "python",\n'
            '      "args": ["-m", "aacf_mcp"]\n'
            "    }\n"
            "  }\n"
            "}\n"
            "```\n\n"
            "**Other IDEs** — add the MCP server config to your IDE's MCP settings:\n"
            "```json\n"
            "{\n"
            '  "aacf": {\n'
            '    "command": "python",\n'
            '    "args": ["-m", "aacf_mcp"]\n'
            "  }\n"
            "}\n"
            "```\n\n"
            "> Requires: `pip install aacf[mcp]`\n\n"
            "## License / 许可证\n\n"
            "SPDX-License-Identifier: GPL-3.0\n",
            encoding="utf-8",
        )

        # 创建 .vscode 目录 — 代码片段 + MCP 配置 / Create .vscode — code snippets + MCP config
        vscode_dir = project_dir / ".vscode"
        vscode_dir.mkdir(exist_ok=True)

        code_snippets = {
            "AACF App Setup": {
                "prefix": ["aacf", "app"],
                "body": [
                    "from aacf import AACF, LLMConfig",
                    "",
                    "app = AACF(__name__, config=LLMConfig(",
                    '    model="${1:qwen2.5-7b-instruct}",',
                    '    url="${2:http://127.0.0.1:8080/v1/chat/completions}",',
                    '    api_key="${3:}",  # Optional for local models / 本地模型可留空',
                    '    language="${4|zh,en|}",',
                    "))",
                    "$0",
                ],
                "description": "快速初始化 AACF 应用实例与全局 LLM 配置",
            },
            "AACF Node Definition": {
                "prefix": ["node", "@app.node"],
                "body": [
                    '@app.node("${1:node_name}").who("${2:专家角色}").what("${3:核心任务描述}")',
                    "def ${4:node_name}(${5:param}: str):",
                    "    pass",
                    "$0",
                ],
                "description": "快速生成 AACF @app.node 智能节点（链式 API 精简版）",
            },
            "AACF Node Full": {
                "prefix": ["nodefull", "@app.node.full"],
                "body": [
                    '@app.node("${1:node_name}")',
                    '    .who("${2:专家角色}")',
                    '    .what("${3:核心任务描述}")',
                    '    .where("${4:业务环境}")',
                    '    .why("${5:执行意图}")',
                    '    .how("${6:操作方法}")',
                    "    .stream(${7|False,True|})",
                    '    .format("${8|text,json|}")',
                    "    .cache(ttl=${9:300})",
                    "    .retry(max_attempts=${10:3})",
                    "def ${11:node_name}(${12:param}: str):",
                    "    pass",
                    "$0",
                ],
                "description": "快速生成 AACF @app.node 智能节点（链式 API 完整版）",
            },
            "AACF Node with Dependency": {
                "prefix": ["nodedep", "@app.node.dep"],
                "body": [
                    '@app.node("${1:downstream}").who("${2:角色}").what("${3:任务}")',
                    "def ${4:downstream}(${5:upstream}: str):  # 参数名匹配上游节点名，自动建立依赖",
                    "    pass",
                    "$0",
                ],
                "description": "生成带依赖关系的 AACF 节点（参数名 = 上游节点名）",
            },
        }
        (vscode_dir / "aacf.code-snippets").write_text(
            json.dumps(code_snippets, indent=4, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        # .vscode/mcp.json — VS Code / Cursor MCP 配置
        (vscode_dir / "mcp.json").write_text(
            json.dumps(
                {
                    "servers": {
                        "aacf": {
                            "command": "python",
                            "args": ["-m", "aacf_mcp"],
                        }
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        # 创建 .qoder/mcp.json — MCP 服务配置 / Create .qoder/mcp.json — MCP server config
        qoder_dir = project_dir / ".qoder"
        qoder_dir.mkdir(exist_ok=True)
        mcp_json = qoder_dir / "mcp.json"
        mcp_json.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "aacf": {
                            "command": "python",
                            "args": ["-m", "aacf_mcp"],
                        }
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        progress.update(task, description="Project structure created / 项目结构已创建")

        # Step 2: Create virtual environment / 创建虚拟环境
        venv_created = False
        if not no_venv:
            task = progress.add_task(description="Creating virtual environment / 创建虚拟环境...", total=None)
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "venv", ".venv"],
                    cwd=str(project_dir),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=30,
                )
                venv_created = True
                progress.update(task, description="Virtual environment created / 虚拟环境已创建")
            except subprocess.TimeoutExpired:
                progress.update(
                    task, description="[yellow]Virtual environment creation timed out / 虚拟环境创建超时[/]"
                )
            except (subprocess.CalledProcessError, Exception):
                progress.update(task, description="[yellow]Virtual environment creation failed / 虚拟环境创建失败[/]")

            # Step 3: Install aacf / 安装 aacf
            if venv_created:
                task = progress.add_task(description="Installing aacf / 安装 aacf...", total=None)
                venv_python = project_dir / ".venv" / "Scripts" / "python.exe"
                if not venv_python.exists():
                    venv_python = project_dir / ".venv" / "bin" / "python"
                try:
                    subprocess.check_call(
                        [str(venv_python), "-m", "pip", "install", "aacf", "-q"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=120,
                    )
                    progress.update(task, description="aacf installed / aacf 已安装")
                except subprocess.TimeoutExpired:
                    progress.update(task, description="[yellow]pip install timed out / pip 安装超时[/]")
                except (subprocess.CalledProcessError, Exception):
                    progress.update(task, description="[yellow]pip install failed / pip 安装失败[/]")

    console.print("[bold green]✔[/] Project structure created / 项目结构已创建。")
    if no_venv:
        console.print("[dim]Skipped virtual environment (--no-venv) / 已跳过虚拟环境创建[/]")
    elif venv_created:
        console.print("[bold green]✔[/] Virtual environment created and aacf installed / 虚拟环境已创建并安装 aacf。")
    else:
        console.print(
            "[bold yellow]⚠[/] Virtual environment creation failed. Please create manually. / 虚拟环境创建失败，请手动创建。"
        )
    console.print(f"\n[bold]Next steps / 下一步:[/]\n  cd {project_name}")
    if venv_created:
        console.print("  .venv\\Scripts\\activate   # Windows")
        console.print("  source .venv/bin/activate  # Linux/macOS")
    console.print("  python main.py")


@app.command()
def run(
    script: str = typer.Argument(..., help="The Python script to run (e.g., main.py) / 要运行的 Python 脚本"),
):
    """Execute an AACF python script with enhanced AI logging.
    执行 AACF Python 脚本，增强 AI 日志输出。"""
    console.print(f"[bold magenta]▶ Running AACF Script / 运行脚本:[/] {script}")

    # 优先使用项目 venv 的 Python / Prefer project venv's Python
    venv_python = Path(".venv") / "Scripts" / "python.exe"
    if not venv_python.exists():
        venv_python = Path(".venv") / "bin" / "python"
    python_exe = str(venv_python) if venv_python.exists() else sys.executable

    try:
        subprocess.check_call([python_exe, script])
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]✖ Script exited with error code / 脚本退出错误码 {e.returncode}[/]")
        raise typer.Exit(code=e.returncode)


@app.command()
def sync(
    path: str = typer.Argument(".", help="Directory or file to scan for @app.node functions / 扫描目录或文件"),
):
    """Scan Python files and inject docstrings to source code for perfect IDE support.
    扫描 Python 文件并向源码注入 docstring，提供完美的 IDE 支持。"""
    console.print(f"[bold magenta]▶ Scanning for @app.node in / 扫描:[/] {path}")
    target_path = Path(path).resolve()

    files_to_scan = []
    if target_path.is_file():
        if target_path.suffix == ".py":
            files_to_scan.append(target_path)
    else:
        files_to_scan = list(target_path.rglob("*.py"))

    count = 0
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        task = progress.add_task(description="Injecting docstrings / 注入文档...", total=len(files_to_scan))
        for py_file in files_to_scan:
            if inject_docstrings_for_file(str(py_file)):
                count += 1
            progress.advance(task)

    if count > 0:
        console.print(
            f"[bold green]✔[/] Successfully injected docstrings for [bold]{count}[/] files / 成功注入 {count} 个文件。"
        )
        console.print(
            "[dim]Your IDE (e.g., Pylance) will now show perfect docstrings and type hints. / IDE 现在将显示完整的文档和类型提示。[/]"
        )
    else:
        console.print("[bold yellow]ℹ[/] No @app.node functions found to sync / 未找到需要同步的 @app.node 函数。")


@app.command()
def doc(
    module: str = typer.Argument("aacf", help="The Python module or directory to document / 要生成文档的模块或目录"),
    port: int = typer.Option(8080, "--port", "-p", help="Port to serve the documentation on / 文档服务端口"),
):
    """Zero-config API documentation server. (Inspired by Rust's cargo doc)
    零配置 API 文档服务器。（灵感来自 Rust 的 cargo doc）"""
    console.print(f"[bold magenta]▶ Starting AACF Doc Server for / 启动文档服务器:[/] {module}")
    console.print(f"[dim]Serving on / 服务地址: http://127.0.0.1:{port}[/]")
    console.print("[dim]Press Ctrl+C to stop / 按 Ctrl+C 停止。[/]")

    try:
        import pdoc  # noqa: F401  # type: ignore
    except ImportError:
        console.print(
            "[bold red]✖ pdoc is not installed. Please run `pip install pdoc`. / pdoc 未安装，请运行 `pip install pdoc`。[/]"
        )
        raise typer.Exit(code=1)

    try:
        import threading

        from pdoc.web import DocServer, open_browser

        def launch():
            time.sleep(1)
            open_browser(f"http://127.0.0.1:{port}")

        threading.Thread(target=launch, daemon=True).start()
        with DocServer(("127.0.0.1", port), [module]) as httpd:
            console.print(f"[bold green]✔[/] Doc server running / 文档服务器运行中: http://127.0.0.1:{port}")
            httpd.serve_forever()
    except KeyboardInterrupt:
        console.print("\n[bold green]✔[/] Doc server stopped / 文档服务器已停止。")
    except Exception as e:
        console.print(f"[bold red]✖ Error starting doc server / 启动文档服务器出错:[/] {e}")
        raise typer.Exit(code=1)


@app.command()
def watch(
    path: str = typer.Argument(".", help="Directory to watch for changes / 监听变化的目录"),
    interval: float = typer.Option(1.0, "--interval", "-i", help="Polling interval in seconds / 轮询间隔（秒）"),
):
    """Watch Python files for changes and automatically inject docstrings.
    监听 Python 文件变化并自动注入 docstring。"""
    console.print(f"[bold magenta]▶ Watching for changes in / 监听:[/] {path}")
    console.print("[dim]Press Ctrl+C to stop / 按 Ctrl+C 停止。[/]")

    target_path = Path(path).resolve()
    last_mtimes = {}

    def get_py_files():
        if target_path.is_file():
            return [target_path] if target_path.suffix == ".py" else []
        return list(target_path.rglob("*.py"))

    for py_file in get_py_files():
        if "typings" in py_file.parts:
            continue
        try:
            last_mtimes[py_file] = os.path.getmtime(py_file)
        except OSError:
            pass

    try:
        while True:
            time.sleep(interval)
            changed_files = []

            for py_file in get_py_files():
                if "typings" in py_file.parts:
                    continue
                try:
                    mtime = os.path.getmtime(py_file)
                    if py_file not in last_mtimes or mtime > last_mtimes[py_file]:
                        changed_files.append(py_file)
                        last_mtimes[py_file] = mtime
                except OSError:
                    pass

            if changed_files:
                console.print(
                    f"\n[bold cyan]Changes detected in {len(changed_files)} file(s). Syncing... / 检测到 {len(changed_files)} 个文件变化，正在同步...[/]"
                )
                count = 0
                for py_file in changed_files:
                    if inject_docstrings_for_file(str(py_file)):
                        count += 1
                if count > 0:
                    console.print(
                        f"[bold green]✔[/] Injected docstrings for [bold]{count}[/] file(s) / 已注入 {count} 个文件。"
                    )
                    # 注入后更新 mtime，避免自身写入触发下一轮检测（防止死循环）
                    # Update mtime after injection to prevent self-write from triggering next detection
                    for py_file in changed_files:
                        try:
                            last_mtimes[py_file] = os.path.getmtime(py_file)
                        except OSError:
                            pass
                else:
                    console.print("[dim]No @app.node updates required / 无需更新 @app.node。[/]")

    except KeyboardInterrupt:
        console.print("\n[bold green]✔[/] Watcher stopped / 监听器已停止。")


if __name__ == "__main__":
    app()
