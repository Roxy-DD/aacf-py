# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 AACF Contributors
"""
MCP Tools: Pipeline Management / 管道管理工具。

Tools for compiling, analyzing, and executing AACF pipelines.
编译、分析和执行 AACF 管道的工具。
"""

import importlib.util
import sys
from pathlib import Path


def _load_project_module(project_path: str):
    """
    Load the agents module from a project directory.
    从项目目录加载 agents 模块。

    Returns the loaded module with all registered nodes.
    返回包含所有已注册节点的模块。
    """
    root = Path(project_path).resolve()
    agents_file = root / "agents.py"
    if not agents_file.exists():
        agents_file = root / "src" / "agents.py"
    if not agents_file.exists():
        raise FileNotFoundError(
            f"No agents.py found in {project_path}. Expected at: {root / 'agents.py'} or {root / 'src' / 'agents.py'}"
        )

    # Use unique module name to avoid conflicts between different projects
    module_name = f"_aacfg_mcp_agents_{root.name}"
    if module_name in sys.modules:
        del sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, agents_file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _get_app_from_module(module):
    """
    Extract the AACF app instance from a loaded module.
    从加载的模块中提取 AACF app 实例。
    """
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        # Check for AACF app instance (has _wrappers and compile method)
        if hasattr(attr, "_wrappers") and hasattr(attr, "compile"):
            return attr
    return None


def _compile_and_get_analyzer(project_path: str):
    """
    Load project, get app, and compile pipeline. Returns (app, analyzer) or error string.
    加载项目、获取 app 并编译管道。返回 (app, analyzer) 或错误字符串。
    """
    module = _load_project_module(project_path)
    app = _get_app_from_module(module)

    if app is None:
        return None, None, "Error: No AACF app instance found in agents.py."

    planner = app.compile()
    analyzer = planner.analyzer

    if analyzer is None:
        return None, None, "Error: Compilation failed - no dependency analyzer created."

    return app, analyzer, None


def register_pipeline_tools(mcp):
    """Register all pipeline management tools with the MCP server."""

    @mcp.tool()
    def compile_pipeline(project_path: str) -> str:
        """
        Compile an AACF project: analyze dependencies and build the DAG.
        编译 AACF 项目：分析依赖关系并构建 DAG。

        Args:
            project_path: Path to the AACF project directory
        """
        try:
            _, analyzer, error = _compile_and_get_analyzer(project_path)
            if error:
                return error

            execution_order = analyzer.get_execution_order()
            parallel_groups = analyzer.get_parallel_groups()

            lines = [
                "Pipeline compiled successfully!",
                "",
                f"Total nodes: {len(execution_order)}",
                "",
                "Execution order (topological):",
            ]
            for i, name in enumerate(execution_order, 1):
                lines.append(f"  {i}. {name}")

            lines.append("")
            lines.append("Parallel groups (can run simultaneously):")
            for i, group in enumerate(parallel_groups, 1):
                lines.append(f"  Group {i}: {', '.join(group)}")

            return "\n".join(lines)

        except Exception as e:
            return f"Compilation failed: {type(e).__name__}: {e}"

    @mcp.tool()
    def get_dependency_graph(project_path: str) -> str:
        """
        Get the DAG dependency graph of an AACF project.
        获取 AACF 项目的 DAG 依赖图。

        Args:
            project_path: Path to the AACF project directory
        """
        try:
            _, analyzer, error = _compile_and_get_analyzer(project_path)
            if error:
                return error

            lines = ["Dependency Graph (DAG):", ""]
            dep_graph = analyzer.get_dependency_graph()

            for node_name in analyzer.get_execution_order():
                deps = dep_graph.get(node_name, set())
                dep_str = ", ".join(sorted(deps)) if deps else "(none)"
                lines.append(f"  {node_name}:")
                lines.append(f"    Depends on: {dep_str}")
                lines.append("")

            return "\n".join(lines)

        except Exception as e:
            return f"Failed to get dependency graph: {type(e).__name__}: {e}"

    @mcp.tool()
    def get_execution_order(project_path: str) -> str:
        """
        Get the topological execution order of nodes.
        获取节点的拓扑执行顺序。

        Args:
            project_path: Path to the AACF project directory
        """
        try:
            _, analyzer, error = _compile_and_get_analyzer(project_path)
            if error:
                return error

            order = analyzer.get_execution_order()
            lines = [f"Execution order ({len(order)} nodes):", ""]
            for i, name in enumerate(order, 1):
                lines.append(f"  {i}. {name}")

            return "\n".join(lines)

        except Exception as e:
            return f"Failed to get execution order: {type(e).__name__}: {e}"

    @mcp.tool()
    def get_parallel_groups(project_path: str) -> str:
        """
        Get parallel execution groups (nodes that can run simultaneously).
        获取并行执行分组（可以同时运行的节点）。

        Args:
            project_path: Path to the AACF project directory
        """
        try:
            _, analyzer, error = _compile_and_get_analyzer(project_path)
            if error:
                return error

            groups = analyzer.get_parallel_groups()
            lines = [f"Parallel groups ({len(groups)} groups):", ""]
            for i, group in enumerate(groups, 1):
                lines.append(f"  Group {i} (parallel): {', '.join(group)}")

            return "\n".join(lines)

        except Exception as e:
            return f"Failed to get parallel groups: {type(e).__name__}: {e}"

    @mcp.tool()
    def run_pipeline(project_path: str, inputs: str = "{}") -> str:
        """
        Execute an AACF pipeline with given inputs.
        使用给定输入执行 AACF 管道。

        Note: This actually runs the pipeline, which may call LLM APIs.
        注意：这会实际运行管道，可能会调用 LLM API。

        Args:
            project_path: Path to the AACF project directory
            inputs: JSON string of input parameters for the pipeline
        """
        import json

        try:
            input_dict = json.loads(inputs) if inputs else {}
        except json.JSONDecodeError as e:
            return f"Invalid JSON inputs: {e}"

        try:
            app, _, error = _compile_and_get_analyzer(project_path)
            if error:
                return error

            # Run the pipeline with inputs parameter
            result = app.run_pipeline(inputs=input_dict)

            return f"Pipeline executed successfully!\n\nResult:\n{result}"

        except Exception as e:
            return f"Pipeline execution failed: {type(e).__name__}: {e}"
