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

from mcp.types import ToolAnnotations


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
    raise FileNotFoundError(f"No agents.py found in {project_path}. Expected at: {candidates[0]} or {candidates[1]}")


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

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Create Node",
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
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
    ) -> dict:
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

        # Build decorator arguments - AACF uses @app.node("name") format
        # followed by chainable methods like .who().what().where()
        dec_args = [f'"{name}"']

        dec_str = ", ".join(dec_args)

        # Build chainable methods
        chain_methods = []
        if who:
            chain_methods.append(f'.who("{who}")')
        if what:
            chain_methods.append(f'.what("{what}")')
        if where:
            chain_methods.append(f'.where("{where}")')
        if why:
            chain_methods.append(f'.why("{why}")')
        if how:
            chain_methods.append(f'.how("{how}")')
        if stream:
            chain_methods.append(".stream(True)")
        if format:
            chain_methods.append(f'.format("{format}")')
        if cache_enabled:
            chain_methods.append(f".cache(ttl={cache_ttl})" if cache_ttl > 0 else ".cache()")
        if max_retries != 3:
            chain_methods.append(f".retry(max_attempts={max_retries})")

        chain_str = "".join(chain_methods) if chain_methods else ""

        # Build node code
        node_code = f"""

@app.node({dec_str}){chain_str}
def {name}(text: str):
    pass
"""

        # Append to agents.py
        with open(agents_file, "a", encoding="utf-8") as f:
            f.write(node_code)

        result = {
            "status": "created",
            "node_name": name,
            "file": str(agents_file),
            "decorator": f"@app.node({dec_str}){chain_str}",
            "function": f"def {name}(text: str): pass",
        }
        return result

    @mcp.tool(
        annotations=ToolAnnotations(
            title="List Nodes",
            readOnlyHint=True,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    def list_nodes(project_path: str) -> dict:
        """
        List all AACF nodes defined in the project.
        列出项目中定义的所有 AACF 节点。

        Args:
            project_path: Path to the AACF project directory
        """
        agents_file = _find_agents_file(project_path)
        nodes = _parse_nodes_from_file(agents_file)

        if not nodes:
            return {"file": str(agents_file), "count": 0, "nodes": []}

        node_list = []
        for n in nodes:
            params = ", ".join(f"{p['name']}: {p['type']}" if p["type"] else p["name"] for p in n["params"])
            node_list.append(
                {
                    "name": n["name"],
                    "line": n["lineno"],
                    "decorator": n["decorator"],
                    "params": params or "(none)",
                    "mode": "LLM auto-call" if not n["has_body_code"] else "Explicit code override",
                    "docstring": n["docstring"].split("\n")[0].strip() if n["docstring"] else "",
                }
            )

        return {"file": str(agents_file), "count": len(node_list), "nodes": node_list}

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Get Node Info",
            readOnlyHint=True,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    def get_node_info(project_path: str, node_name: str) -> dict:
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
            if n["name"] == node_name:
                target = n
                break

        if target is None:
            available = [n["name"] for n in nodes]
            return {"error": f"Node '{node_name}' not found", "available_nodes": available}

        params = []
        for p in target["params"]:
            params.append({"name": p["name"], "type": p["type"] or None})

        return {
            "name": target["name"],
            "file": str(agents_file),
            "line": target["lineno"],
            "decorator": target["decorator"],
            "mode": "LLM auto-call (pass)" if not target["has_body_code"] else "Explicit code override",
            "params": params,
            "docstring": target["docstring"] or None,
        }

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Configure Node",
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
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
    ) -> dict:
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

        # Find the node's decorator - handle both old and new format
        # New format: @app.node("name").who(...).what(...).cache(...)
        # Old format: @app.node(who="...", what="...")
        # Match only the decorator line(s), not the function definition
        dec_pattern = rf"(@app\.node\([^)]*\)(?:\.[\w]+\([^)]*\))*)\s*\n\s*def\s+{re.escape(node_name)}"
        dec_match = re.search(dec_pattern, source, re.DOTALL)

        if not dec_match:
            # Try simpler pattern to check if node exists
            pattern2 = rf"def\s+{re.escape(node_name)}\s*\("
            if not re.search(pattern2, source):
                return {"error": f"Node '{node_name}' not found in {agents_file.name}"}
            return {
                "error": f"Node '{node_name}' found but decorator could not be parsed for automatic reconfiguration.",
                "hint": f"Please manually edit the decorator in {agents_file.name}.",
            }

        # Extract the full decorator line (group 1 is the decorator only)
        full_decorator = dec_match.group(1)

        # Parse existing chainable methods
        # Extract the base @app.node("name") part
        base_match = re.match(r"@app\.node\(([^)]*)\)", full_decorator)
        if not base_match:
            return {"error": f"Could not parse base decorator for node '{node_name}'."}

        node_name_arg = base_match.group(1).strip()

        # Extract existing chainable methods
        chain_methods = re.findall(r"\.(\w+)\(([^)]*)\)", full_decorator[len(base_match.group(0)) :])

        # Build new chain methods, replacing existing ones with same name
        new_chains = {}
        for method_name, method_args in chain_methods:
            new_chains[method_name] = method_args

        # Apply overrides
        if cache_enabled is not None:
            if cache_ttl is not None:
                new_chains["cache"] = f"ttl={cache_ttl}"
            else:
                new_chains["cache"] = ""
        if max_retries is not None:
            if retry_delay is not None:
                new_chains["retry"] = f"max_attempts={max_retries}, delay={retry_delay}"
            else:
                new_chains["retry"] = f"max_attempts={max_retries}"
        if timeout is not None:
            new_chains["timeout"] = str(timeout)
        if stream is not None:
            new_chains["stream"] = str(stream).lower()
        if format is not None:
            new_chains["format"] = f'"{format}"'

        # Build new decorator
        new_decorator = f"@app.node({node_name_arg})"
        for method_name, method_args in new_chains.items():
            if method_args:
                new_decorator += f".{method_name}({method_args})"
            else:
                new_decorator += f".{method_name}()"

        # Replace old decorator with new one
        new_source = source.replace(full_decorator, new_decorator, 1)
        agents_file.write_text(new_source, encoding="utf-8")

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

        return {
            "status": "updated",
            "node_name": node_name,
            "file": str(agents_file),
            "new_decorator": new_decorator,
            "changes": changes,
        }
