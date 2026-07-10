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

from mcp.types import ToolAnnotations


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

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Compile Pipeline",
            readOnlyHint=True,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    def compile_pipeline(project_path: str) -> dict:
        """
        Compile an AACF project: analyze dependencies and build the DAG.
        编译 AACF 项目：分析依赖关系并构建 DAG。

        Args:
            project_path: Path to the AACF project directory
        """
        try:
            _, analyzer, error = _compile_and_get_analyzer(project_path)
            if error:
                return {"error": error}

            execution_order = analyzer.get_execution_order()
            parallel_groups = analyzer.get_parallel_groups()

            return {
                "status": "compiled",
                "total_nodes": len(execution_order),
                "execution_order": execution_order,
                "parallel_groups": [{"group": i + 1, "nodes": list(group)} for i, group in enumerate(parallel_groups)],
            }

        except Exception as e:
            return {"error": f"Compilation failed: {type(e).__name__}: {e}"}

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Get Dependency Graph",
            readOnlyHint=True,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    def get_dependency_graph(project_path: str) -> dict:
        """
        Get the DAG dependency graph of an AACF project.
        获取 AACF 项目的 DAG 依赖图。

        Args:
            project_path: Path to the AACF project directory
        """
        try:
            _, analyzer, error = _compile_and_get_analyzer(project_path)
            if error:
                return {"error": error}

            dep_graph = analyzer.get_dependency_graph()
            execution_order = analyzer.get_execution_order()

            graph = {}
            for node_name in execution_order:
                deps = dep_graph.get(node_name, set())
                graph[node_name] = {"depends_on": sorted(deps)}

            return {"graph": graph}

        except Exception as e:
            return {"error": f"Failed to get dependency graph: {type(e).__name__}: {e}"}

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Get Execution Order",
            readOnlyHint=True,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    def get_execution_order(project_path: str) -> dict:
        """
        Get the topological execution order of nodes.
        获取节点的拓扑执行顺序。

        Args:
            project_path: Path to the AACF project directory
        """
        try:
            _, analyzer, error = _compile_and_get_analyzer(project_path)
            if error:
                return {"error": error}

            order = analyzer.get_execution_order()
            return {"node_count": len(order), "execution_order": order}

        except Exception as e:
            return {"error": f"Failed to get execution order: {type(e).__name__}: {e}"}

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Get Parallel Groups",
            readOnlyHint=True,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    def get_parallel_groups(project_path: str) -> dict:
        """
        Get parallel execution groups (nodes that can run simultaneously).
        获取并行执行分组（可以同时运行的节点）。

        Args:
            project_path: Path to the AACF project directory
        """
        try:
            _, analyzer, error = _compile_and_get_analyzer(project_path)
            if error:
                return {"error": error}

            groups = analyzer.get_parallel_groups()
            return {
                "group_count": len(groups),
                "parallel_groups": [{"group": i + 1, "nodes": list(group)} for i, group in enumerate(groups)],
            }

        except Exception as e:
            return {"error": f"Failed to get parallel groups: {type(e).__name__}: {e}"}

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Run Pipeline",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=True,
        ),
    )
    def run_pipeline(project_path: str, inputs: str = "{}") -> dict:
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
            return {"error": f"Invalid JSON inputs: {e}"}

        try:
            app, _, error = _compile_and_get_analyzer(project_path)
            if error:
                return {"error": error}

            # Run the pipeline with inputs parameter
            result = app.run_pipeline(inputs=input_dict)

            return {"status": "success", "results": result}

        except Exception as e:
            return {"error": f"Pipeline execution failed: {type(e).__name__}: {e}"}
