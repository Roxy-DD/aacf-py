# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 AACF Contributors
"""
MCP Prompts — reusable message templates for AI-assisted development.
MCP 提示 — 用于 AI 辅助开发的可复用消息模板。

Prompts help AI clients generate better responses by providing
structured context about common AACF development tasks.
提示帮助 AI 客户端通过提供有关常见 AACF 开发任务的结构化上下文来生成更好的响应。
"""


def register_prompts(mcp):
    """Register all prompts with the MCP server."""

    @mcp.prompt()
    def create_node_plan(project_path: str, node_name: str, role: str, task: str) -> list[dict]:
        """
        Generate a plan for creating a new AACF node with proper configuration.
        生成创建新 AACF 节点的计划，包含正确的配置。

        Args:
            project_path: Path to the AACF project
            node_name: Name of the node to create
            role: Agent role description
            task: Core task description
        """
        return [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": (
                        f"I need to create a new AACF node in my project at '{project_path}'.\n\n"
                        f"Node name: {node_name}\n"
                        f"Agent role: {role}\n"
                        f"Core task: {task}\n\n"
                        "Please:\n"
                        "1. Use the create_node tool to add this node\n"
                        "2. Consider what dependencies it might need (params matching upstream node names)\n"
                        "3. Suggest appropriate cache/retry settings if applicable\n"
                        "4. Show me how to call it from main.py"
                    ),
                },
            }
        ]

    @mcp.prompt()
    def debug_pipeline(project_path: str) -> list[dict]:
        """
        Analyze and debug an AACF pipeline configuration.
        分析并调试 AACF 管道配置。

        Args:
            project_path: Path to the AACF project
        """
        return [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": (
                        f"Please analyze my AACF project at '{project_path}' and help me debug:\n\n"
                        "1. Read the project structure and agents.py\n"
                        "2. Compile the pipeline to check for dependency issues\n"
                        "3. Show the dependency graph and execution order\n"
                        "4. Identify any circular dependencies or missing connections\n"
                        "5. Suggest improvements to the pipeline structure\n\n"
                        "Use the available tools (read_project, compile_pipeline, "
                        "get_dependency_graph, get_execution_order) to investigate."
                    ),
                },
            }
        ]

    @mcp.prompt()
    def explain_chain_api() -> list[dict]:
        """
        Explain the AACF chainable API with examples.
        用示例解释 AACF 链式 API。
        """
        return [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": (
                        "Please explain the AACF chainable API for configuring nodes. "
                        "Include:\n\n"
                        '1. Basic decorator syntax: @app.node("name")\n'
                        "2. All available chain methods with descriptions:\n"
                        "   .who(), .what(), .where(), .why(), .how(),\n"
                        "   .stream(), .format(), .out(), .cache(), .retry(), .timeout()\n"
                        "3. A complete example with multiple nodes showing dependencies\n"
                        "4. The dependency convention (param name = upstream node name)\n"
                        "5. When to use pass (LLM auto-call) vs explicit code"
                    ),
                },
            }
        ]

    @mcp.prompt()
    def optimize_project(project_path: str) -> list[dict]:
        """
        Analyze a project and suggest optimizations.
        分析项目并建议优化方案。

        Args:
            project_path: Path to the AACF project
        """
        return [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": (
                        f"Please analyze my AACF project at '{project_path}' and suggest optimizations:\n\n"
                        "1. Read agents.py and identify nodes that could benefit from caching\n"
                        "2. Check the dependency graph for parallelization opportunities\n"
                        "3. Review node configurations (retry, timeout, streaming)\n"
                        "4. Suggest any missing chain methods that would improve reliability\n"
                        "5. Check if the pipeline structure follows best practices\n\n"
                        "Use read_project, list_nodes, compile_pipeline, and get_parallel_groups tools."
                    ),
                },
            }
        ]

    @mcp.prompt()
    def migrate_to_chain_api(project_path: str) -> list[dict]:
        """
        Help migrate old kwargs-style decorators to the new chain API.
        帮助将旧的 kwargs 风格装饰器迁移到新的链式 API。

        Args:
            project_path: Path to the AACF project
        """
        return [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": (
                        f"My AACF project at '{project_path}' may have old-style decorators "
                        "using kwargs format like:\n"
                        '  @app.node(who="Translator", what="Translate text")\n\n'
                        "Please:\n"
                        "1. Read agents.py and identify any old-style decorators\n"
                        "2. Convert them to the new chain API format:\n"
                        '  @app.node("name").who("Translator").what("Translate text")\n'
                        "3. Use configure_node or suggest manual edits as needed\n"
                        "4. Verify the migration by listing all nodes afterward"
                    ),
                },
            }
        ]
