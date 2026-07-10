# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 AACF Contributors
"""
AACF MCP Server -- Model Context Protocol server for AACF.

Exposes AACF core operations as MCP Tools so AI clients
(Claude Desktop, VS Code Copilot, etc.) can assist users
in building and managing AACF projects.

导出 / Exports:
    create_server: 创建并配置 MCP Server 实例
"""

from aacf_mcp.server import create_server

__all__ = ["create_server"]
