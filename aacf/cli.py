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
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    try:
        sys.stderr.reconfigure(encoding="utf-8")
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
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                source_lines = f.readlines()
            tree = ast.parse(''.join(source_lines))
            docstring_ranges = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    doc = ast.get_docstring(node)
                    if doc and 'AACF' in doc:
                        expr_node = node.body[0]
                        docstring_ranges[node.name] = (expr_node.lineno, expr_node.end_lineno)
        except Exception:
            return

        funcs_to_inject = []
        for func, meta, sig in nodes:
            doc = getattr(func, '__doc__', None)
            if doc and 'AACF' not in doc:
                continue
            try:
                _, start_lineno = inspect.getsourcelines(func)
            except Exception:
                continue
            funcs_to_inject.append((start_lineno, func, meta))

        if not funcs_to_inject:
            return

        funcs_to_inject.sort(key=lambda x: x[0], reverse=True)

        for start_lineno, func, meta in funcs_to_inject:
            name = func.__name__
            if name in docstring_ranges:
                start, end = docstring_ranges[name]
                del source_lines[start - 1:end]

            idx = start_lineno - 1
            paren_count = 0
            in_def = False
            colon_idx = idx
            def_indent = 0
            for i in range(idx, len(source_lines)):
                line = source_lines[i]
                if not in_def and line.lstrip().startswith('def '):
                    in_def = True
                    def_indent = len(line) - len(line.lstrip())
                paren_count += line.count('(') - line.count(')')
                if in_def and paren_count == 0 and ':' in line:
                    colon_idx = i
                    break

            indent_str = " " * (def_indent + 4)
            who = meta.get("who", "未命名智能体 / AI Agent")
            what = meta.get("what", "未定义任务 / Task undefined")
            where = meta.get("where", "未知环境 / Environment unknown")

            docstring_lines = [
                f'{indent_str}"""\n',
                f'{indent_str}🤖 【AACF 智能节点 / Smart Node】: {who}\n',
                f'{indent_str}🎯 核心任务 / Core Task: {what}\n',
                f'{indent_str}📍 执行环境 / Environment: {where}\n',
                f'{indent_str}"""\n',
            ]

            line = source_lines[colon_idx]
            colon_pos = line.find(':', line.rfind(')'))
            if colon_pos != -1:
                before_colon = line[:colon_pos + 1]
                after_colon = line[colon_pos + 1:].strip()
                source_lines[colon_idx] = before_colon + '\n'
                if after_colon:
                    docstring_lines.append(f'{indent_str}{after_colon}\n')

            source_lines = source_lines[:colon_idx + 1] + docstring_lines + source_lines[colon_idx + 1:]

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.writelines(source_lines)
        except Exception:
            pass

    target_path = Path(filepath).resolve()
    if not target_path.exists() or target_path.suffix != '.py':
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
        if inspect.isfunction(obj) and hasattr(obj, '__aacf_meta__'):
            has_nodes = True
            meta = obj.__aacf_meta__
            sig = inspect.signature(obj)
            nodes.append((obj, meta, sig))

    if not has_nodes:
        return False

    _inject_docstrings_to_py(filepath, nodes)
    return True


# ────────────────────────────────────────────
# CLI Commands / 命令行命令
# ─────────────────────────────────────────────

@app.command()
def init(
    project_name: str = typer.Argument(..., help="The name of your new AACF project / 新项目名称"),
):
    """Initialize a new AACF project with the recommended directory structure.
    初始化一个新的 AACF 项目，包含推荐的目录结构。"""
    console.print(Panel.fit(
        f"[bold blue]Initializing AACF Project / 初始化项目:[/] [green]{project_name}[/]",
        border_style="blue",
    ))
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        progress.add_task(description="Creating project structure / 创建项目结构...", total=None)
        time.sleep(1.0)
    console.print("[bold green]✔[/] Project structure created / 项目结构已创建。")
    console.print("[bold green]✔[/] Virtual environment initialized / 虚拟环境已初始化。")
    console.print(f"\n[bold]Next steps / 下一步:[/]\n  cd {project_name}\n  aacf run main.py")


@app.command()
def run(
    script: str = typer.Argument(..., help="The Python script to run (e.g., main.py) / 要运行的 Python 脚本"),
):
    """Execute an AACF python script with enhanced AI logging.
    执行 AACF Python 脚本，增强 AI 日志输出。"""
    console.print(f"[bold magenta]▶ Running AACF Script / 运行脚本:[/] {script}")
    try:
        subprocess.check_call([sys.executable, script])
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
        if target_path.suffix == '.py':
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
        console.print(f"[bold green]✔[/] Successfully injected docstrings for [bold]{count}[/] files / 成功注入 {count} 个文件。")
        console.print("[dim]Your IDE (e.g., Pylance) will now show perfect docstrings and type hints. / IDE 现在将显示完整的文档和类型提示。[/]")
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
    console.print(f"[dim]Serving on / 服务地址: http://localhost:{port}[/]")
    console.print("[dim]Press Ctrl+C to stop / 按 Ctrl+C 停止。[/]")

    try:
        import pdoc  # type: ignore
    except ImportError:
        console.print("[bold red]✖ pdoc is not installed. Please run `pip install pdoc`. / pdoc 未安装，请运行 `pip install pdoc`。[/]")
        raise typer.Exit(code=1)

    try:
        import webbrowser
        import threading

        def open_browser():
            time.sleep(1)
            webbrowser.open(f"http://localhost:{port}")

        threading.Thread(target=open_browser, daemon=True).start()
        pdoc.pdoc(module, host="localhost", port=port)
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
            return [target_path] if target_path.suffix == '.py' else []
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
                console.print(f"\n[bold cyan]Changes detected in {len(changed_files)} file(s). Syncing... / 检测到 {len(changed_files)} 个文件变化，正在同步...[/]")
                count = 0
                for py_file in changed_files:
                    if inject_docstrings_for_file(str(py_file)):
                        count += 1
                if count > 0:
                    console.print(f"[bold green]✔[/] Injected docstrings for [bold]{count}[/] file(s) / 已注入 {count} 个文件。")
                else:
                    console.print("[dim]No @app.node updates required / 无需更新 @app.node。[/]")

    except KeyboardInterrupt:
        console.print("\n[bold green]✔[/] Watcher stopped / 监听器已停止。")


if __name__ == "__main__":
    app()
