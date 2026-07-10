# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 AACF Contributors
"""
MCP Resources — expose project data as readable resources.
MCP 资源 — 将项目数据暴露为可读取的资源。

Resources allow MCP clients to read project files and metadata
via standardized URIs, without invoking tools.
资源允许 MCP 客户端通过标准化 URI 读取项目文件和元数据，无需调用工具。
"""

from pathlib import Path


def register_resources(mcp):
    """Register all resources with the MCP server."""

    @mcp.resource("aacf://{project_name}/structure")
    def get_project_structure(project_name: str) -> str:
        """
        Get the project's file structure overview.
        获取项目的文件结构概览。

        Args:
            project_name: Name of the AACF project directory
        """
        root = Path(project_name).resolve()
        if not root.exists():
            return f"Error: Project directory '{project_name}' does not exist."

        exclude_dirs = {".venv", "venv", "__pycache__", ".git", "node_modules", ".qoder"}
        lines = [f"Project: {root.name}", f"Path: {root}", ""]

        for item in sorted(root.rglob("*")):
            if any(excluded in item.parts for excluded in exclude_dirs):
                continue
            if item.name.startswith(".") and item.name not in (".gitignore", ".qoder"):
                continue
            rel = item.relative_to(root)
            if item.is_dir():
                lines.append(f"  {rel}/")
            else:
                size = item.stat().st_size
                lines.append(f"  {rel} ({size} bytes)")

        return "\n".join(lines)

    @mcp.resource("aacf://{project_name}/agents")
    def get_agents_content(project_name: str) -> str:
        """
        Get the full content of agents.py (node definitions).
        获取 agents.py 的完整内容（节点定义）。

        Args:
            project_name: Name of the AACF project directory
        """
        root = Path(project_name).resolve()
        agents_file = root / "agents.py"
        if not agents_file.exists():
            agents_file = root / "src" / "agents.py"
        if not agents_file.exists():
            return f"Error: agents.py not found in '{project_name}'."
        return agents_file.read_text(encoding="utf-8")

    @mcp.resource("aacf://{project_name}/main")
    def get_main_content(project_name: str) -> str:
        """
        Get the full content of main.py (entry point).
        获取 main.py 的完整内容（入口文件）。

        Args:
            project_name: Name of the AACF project directory
        """
        root = Path(project_name).resolve()
        main_file = root / "main.py"
        if not main_file.exists():
            return f"Error: main.py not found in '{project_name}'."
        return main_file.read_text(encoding="utf-8")

    @mcp.resource("aacf://{project_name}/readme")
    def get_readme_content(project_name: str) -> str:
        """
        Get the full content of README.md.
        获取 README.md 的完整内容。

        Args:
            project_name: Name of the AACF project directory
        """
        root = Path(project_name).resolve()
        readme_file = root / "README.md"
        if not readme_file.exists():
            return f"Error: README.md not found in '{project_name}'."
        return readme_file.read_text(encoding="utf-8")

    @mcp.resource("aacf://{project_name}/config")
    def get_project_config(project_name: str) -> str:
        """
        Get project configuration summary (LLMConfig, nodes, dependencies).
        获取项目配置摘要（LLM 配置、节点、依赖关系）。

        Args:
            project_name: Name of the AACF project directory
        """
        import ast

        root = Path(project_name).resolve()
        agents_file = root / "agents.py"
        if not agents_file.exists():
            agents_file = root / "src" / "agents.py"
        if not agents_file.exists():
            return f"Error: agents.py not found in '{project_name}'."

        source = agents_file.read_text(encoding="utf-8")
        tree = ast.parse(source)

        config_info = {"model": "", "url": "", "language": ""}
        nodes = []

        for node in ast.walk(tree):
            # Extract LLMConfig
            if isinstance(node, ast.Call):
                func_str = ast.unparse(node.func) if hasattr(node.func, "id") or hasattr(node.func, "attr") else ""
                if "LLMConfig" in func_str:
                    for kw in node.keywords:
                        if kw.arg in ("model", "url", "language"):
                            if isinstance(kw.value, ast.Constant):
                                config_info[kw.arg] = str(kw.value.value)

            # Extract node names
            if isinstance(node, ast.FunctionDef):
                for dec in node.decorator_list:
                    dec_str = ast.unparse(dec)
                    if "app.node" in dec_str:
                        params = [arg.arg for arg in node.args.args if arg.arg != "self"]
                        nodes.append({"name": node.name, "params": params, "line": node.lineno})

        lines = [
            "Project Configuration Summary / 项目配置摘要:",
            "",
            "LLM Config:",
            f"  Model: {config_info['model'] or '(not set)'}",
            f"  URL: {config_info['url'] or '(not set)'}",
            f"  Language: {config_info['language'] or '(default)'}",
            "",
            f"Nodes ({len(nodes)}):",
        ]
        for n in nodes:
            params_str = ", ".join(n["params"]) or "(none)"
            lines.append(f"  - {n['name']}({params_str}) [line {n['line']}]")

        return "\n".join(lines)
