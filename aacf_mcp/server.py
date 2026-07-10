# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 AACF Contributors
"""
AACF MCP Server -- Model Context Protocol server for AACF.

Exposes AACF core operations as MCP Tools so AI clients
(Claude Desktop, VS Code Copilot, etc.) can assist users
in building and managing AACF projects.

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
        Configured FastMCP server with all tools registered.
    """
    mcp = FastMCP("AACF Server")

    # Register all tool modules
    from aacf_mcp.tools.nodes import register_node_tools
    from aacf_mcp.tools.pipeline import register_pipeline_tools
    from aacf_mcp.tools.project import register_project_tools

    register_node_tools(mcp)
    register_pipeline_tools(mcp)
    register_project_tools(mcp)

    return mcp


def main():
    """Main entry point for the MCP server (stdio transport)."""
    server = create_server()
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
