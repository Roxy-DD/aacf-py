# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 AACF Contributors
"""
MCP Tools: Node Management / 节点管理工具。

Tools for creating, listing, inspecting, and configuring AACF nodes.
创建、列出、查看和配置 AACF 节点的工具。
"""

import ast
import re
from pathlib import Path
from typing import Optional


def _find_agents_file(project_path: str) -> Path:
    """
    Locate the agents.py file in a project.
    在项目中定位 agents.py 文件。

    Searches project root first, then src/ subdirectory.
    先搜索项目根目录，再搜索 src/ 子目录。
    """
    root = Path(project_path).resolve()
    candidates = [root / "agents.py", root / "src" / "agents.py"]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(
        f"No agents.py found in {project_path}. "
        f"Expected at: {candidates[0]} or {candidates[1]}"
    )


def _parse_nodes_from_file(filepath: Path) -> list[dict]:
    """
    Parse @app.node decorated functions from a Python file.
    从 Python 文件中解析 @app.node 装饰的函数。

    Returns a list of dicts with node metadata.
    返回包含节点元数据的字典列表。
    """
    source = filepath.read_text(encoding="utf-8")
    tree = ast.parse(source)

    nodes = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue

        # Check for @app.node(...) decorator
        decorator_info = None
        for dec in node.decorator_list:
            dec_str = ast.unparse(dec)
            if "app.node" in dec_str or ".node(" in dec_str:
                decorator_info = dec_str
                break

        if decorator_info is None:
            continue

        # Extract parameters from decorator
        info = {
            "name": node.name,
            "decorator": decorator_info,
            "params": [],
            "has_body_code": False,
            "docstring": ast.get_docstring(node) or "",
            "lineno": node.lineno,
        }

        # Get function parameters
        for arg in node.args.args:
            if arg.arg == "self":
                continue
            annotation = ""
            if arg.annotation:
                annotation = ast.unparse(arg.annotation)
            info["params"].append({"name": arg.arg, "type": annotation})

        # Check if body is just pass
        body = node.body
        if len(body) == 1 and isinstance(body[0], ast.Pass):
            info["has_body_code"] = False
        elif len(body) == 2:
            if isinstance(body[0], ast.Expr) and isinstance(body[1], ast.Pass):
                info["has_body_code"] = False
            else:
                info["has_body_code"] = True
        else:
            info["has_body_code"] = True

        nodes.append(info)

    return nodes


def register_node_tools(mcp):
    """Register all node management tools with the MCP server."""

    @mcp.tool()
    def create_node(
        project_path: str,
        name: str,
        who: str,
        what: str,
        where: str = "",
        why: str = "",
        how: str = "",
        stream: bool = False,
        format: str = "",
        cache_enabled: bool = False,
        cache_ttl: int = 0,
        max_retries: int = 3,
    ) -> str:
        """
        Create a new AACF node in the project's agents.py file.
        在项目的 agents.py 文件中创建一个新的 AACF 节点。

        Args:
            project_path: Path to the AACF project directory
            name: Node/function name (must be valid Python identifier)
            who: Agent role (e.g., "Translator", "Data Analyst")
            what: Core task description
            where: Business context (optional)
            why: Execution intent (optional)
            how: Steps or constraints (optional)
            stream: Enable streaming output (default: False)
            format: Output format, "json" for JSON mode (optional)
            cache_enabled: Enable result caching (default: False)
            cache_ttl: Cache TTL in seconds, 0 = no expiry (default: 0)
            max_retries: Max retry attempts (default: 3)
        """
        agents_file = _find_agents_file(project_path)

        # Build decorator arguments
        dec_args = [f'who="{who}"', f'what="{what}"']
        if where:
            dec_args.append(f'where="{where}"')
        if why:
            dec_args.append(f'why="{why}"')
        if how:
            dec_args.append(f'how="{how}"')
        if stream:
            dec_args.append("stream=True")
        if format:
            dec_args.append(f'format="{format}"')
        if cache_enabled:
            dec_args.append("cache_enabled=True")
            if cache_ttl > 0:
                dec_args.append(f"cache_ttl={cache_ttl}")
        if max_retries != 3:
            dec_args.append(f"max_retries={max_retries}")

        dec_str = ", ".join(dec_args)

        # Build node code
        node_code = f"""

@app.node({dec_str})
def {name}(text: str):
    pass
"""

        # Append to agents.py
        with open(agents_file, "a", encoding="utf-8") as f:
            f.write(node_code)

        return (
            f"Node '{name}' created successfully in {agents_file.name}.\n"
            f"Decorator: @app.node({dec_str})\n"
            f"Function: def {name}(text: str): pass"
        )

    @mcp.tool()
    def list_nodes(project_path: str) -> str:
        """
        List all AACF nodes defined in the project.
        列出项目中定义的所有 AACF 节点。

        Args:
            project_path: Path to the AACF project directory
        """
        agents_file = _find_agents_file(project_path)
        nodes = _parse_nodes_from_file(agents_file)

        if not nodes:
            return f"No @app.node decorated functions found in {agents_file.name}."

        lines = [f"Found {len(nodes)} node(s) in {agents_file.name}:\n"]
        for i, n in enumerate(nodes, 1):
            lines.append(f"  {i}. {n['name']} (line {n['lineno']})")
            lines.append(f"     Decorator: {n['decorator']}")
            params = ", ".join(
                f"{p['name']}: {p['type']}" if p['type'] else p['name']
                for p in n['params']
            )
            lines.append(f"     Params: {params or '(none)'}")
            mode = "LLM auto-call" if not n['has_body_code'] else "Explicit code override"
            lines.append(f"     Mode: {mode}")
            if n['docstring']:
                first_line = n['docstring'].split('\n')[0].strip()
                lines.append(f"     Doc: {first_line}")
            lines.append("")

        return "\n".join(lines)

    @mcp.tool()
    def get_node_info(project_path: str, node_name: str) -> str:
        """
        Get detailed information about a specific AACF node.
        获取特定 AACF 节点的详细信息。

        Args:
            project_path: Path to the AACF project directory
            node_name: Name of the node/function to inspect
        """
        agents_file = _find_agents_file(project_path)
        nodes = _parse_nodes_from_file(agents_file)

        target = None
        for n in nodes:
            if n['name'] == node_name:
                target = n
                break

        if target is None:
            available = ", ".join(n['name'] for n in nodes)
            return (
                f"Node '{node_name}' not found in {agents_file.name}.\n"
                f"Available nodes: {available or '(none)'}"
            )

        lines = [
            f"Node: {target['name']}",
            f"File: {agents_file.name} (line {target['lineno']})",
            f"Decorator: {target['decorator']}",
            f"Mode: {'LLM auto-call (pass)' if not target['has_body_code'] else 'Explicit code override'}",
            "",
            "Parameters:",
        ]
        for p in target['params']:
            type_str = f": {p['type']}" if p['type'] else ""
            lines.append(f"  - {p['name']}{type_str}")

        if target['docstring']:
            lines.append("")
            lines.append("Docstring:")
            for line in target['docstring'].split('\n'):
                lines.append(f"  {line}")

        return "\n".join(lines)

    @mcp.tool()
    def configure_node(
        project_path: str,
        node_name: str,
        cache_enabled: Optional[bool] = None,
        cache_ttl: Optional[int] = None,
        max_retries: Optional[int] = None,
        retry_delay: Optional[float] = None,
        timeout: Optional[int] = None,
        stream: Optional[bool] = None,
        format: Optional[str] = None,
    ) -> str:
        """
        Modify configuration of an existing AACF node.
        修改现有 AACF 节点的配置。

        Only specified parameters will be updated; others remain unchanged.
        只更新指定的参数，其他保持不变。

        Args:
            project_path: Path to the AACF project directory
            node_name: Name of the node to configure
            cache_enabled: Enable/disable result caching
            cache_ttl: Cache TTL in seconds
            max_retries: Max retry attempts
            retry_delay: Delay between retries in seconds
            timeout: Execution timeout in seconds
            stream: Enable/disable streaming output
            format: Output format ("json" for JSON mode)
        """
        agents_file = _find_agents_file(project_path)
        source = agents_file.read_text(encoding="utf-8")

        # Find the node's decorator line
        pattern = rf'(@app\.node\([^)]*def\s+{re.escape(node_name)}\s*\()'
        match = re.search(pattern, source, re.DOTALL)
        if not match:
            # Try simpler pattern
            pattern2 = rf'def\s+{re.escape(node_name)}\s*\('
            if not re.search(pattern2, source):
                return f"Node '{node_name}' not found in {agents_file.name}."
            return (
                f"Node '{node_name}' found but its @app.node decorator "
                f"could not be parsed for automatic reconfiguration.\n"
                f"Please manually edit the decorator in {agents_file.name}."
            )

        # Build new decorator args from existing + overrides
        # Extract current decorator
        dec_pattern = rf'@app\.node\(([^)]*)\)\s*\n\s*def\s+{re.escape(node_name)}'
        dec_match = re.search(dec_pattern, source, re.DOTALL)
        if not dec_match:
            return (
                f"Could not parse decorator for node '{node_name}'. "
                f"Please manually edit {agents_file.name}."
            )

        current_args = dec_match.group(1).strip()

        # Parse existing args and apply overrides
        changes = []
        if cache_enabled is not None:
            changes.append(f"cache_enabled={cache_enabled}")
        if cache_ttl is not None:
            changes.append(f"cache_ttl={cache_ttl}")
        if max_retries is not None:
            changes.append(f"max_retries={max_retries}")
        if retry_delay is not None:
            changes.append(f"retry_delay={retry_delay}")
        if timeout is not None:
            changes.append(f"timeout={timeout}")
        if stream is not None:
            changes.append(f"stream={stream}")
        if format is not None:
            changes.append(f'format="{format}"')

        if not changes:
            return "No configuration changes specified."

        # Simple approach: append new args to existing decorator
        new_args = current_args.rstrip().rstrip(",")
        if new_args:
            new_args += ", "
        new_args += ", ".join(changes)

        old_dec = f"@app.node({current_args})"
        new_dec = f"@app.node({new_args})"
        new_source = source.replace(old_dec, new_dec, 1)

        agents_file.write_text(new_source, encoding="utf-8")

        return (
            f"Node '{node_name}' configuration updated in {agents_file.name}.\n"
            f"Changes: {', '.join(changes)}"
        )
