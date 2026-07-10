# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 AACF Contributors
"""
AACF MCP Server -- Model Context Protocol server for AACF.

Exposes AACF core operations as MCP Tools, Resources, and Prompts
so AI clients (Claude Desktop, VS Code Copilot, Qoder, etc.) can
assist users in building and managing AACF projects.

Usage:
    aacf-mcp                  # stdio mode (for AI clients)
    python -m aacf_mcp        # stdio mode (for AI clients)
"""

from mcp.server.fastmcp import FastMCP


def create_server() -> FastMCP:
    """
    Create and configure the AACF MCP Server instance.
    创建并配置 AACF MCP Server 实例。

    Returns:
        Configured FastMCP server with all tools, resources, and prompts registered.
    """
    mcp = FastMCP(
        "AACF Server",
        instructions=(
            "AACF (Agentic AI Compiler Framework) MCP Server.\n"
            "Helps users build AI agent pipelines with the chainable decorator API.\n\n"
            "Key concepts:\n"
            "- Nodes: AI agent functions decorated with @app.node()\n"
            "- Chain API: .who().what().where().cache().retry() etc.\n"
            "- Dependencies: param name matching upstream node name\n"
            "- Pipeline: auto-resolved DAG from node dependencies\n\n"
            "Use Resources to read project data, Tools to modify/execute, "
            "and Prompts for guided workflows."
        ),
    )

    # Register tool modules
    from aacf_mcp.tools.nodes import register_node_tools
    from aacf_mcp.tools.pipeline import register_pipeline_tools
    from aacf_mcp.tools.project import register_project_tools

    register_node_tools(mcp)
    register_pipeline_tools(mcp)
    register_project_tools(mcp)

    # Register resources
    from aacf_mcp.tools.resources import register_resources

    register_resources(mcp)

    # Register prompts
    from aacf_mcp.tools.prompts import register_prompts

    register_prompts(mcp)

    return mcp


def main():
    """Main entry point for the MCP server (stdio transport)."""
    server = create_server()
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
