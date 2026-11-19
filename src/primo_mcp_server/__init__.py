"""Primo MCP Server -- search Towson University's Albert S. Cook Library (OneSearch).

Adapted from Aaron Tay's SMU fork of geheharidas/primo-mcp-server (MIT).
"""

__version__ = "0.1.0"


def main() -> None:
    """Entry point for the primo-mcp-server command."""
    from primo_mcp_server.server import mcp

    mcp.run(transport="stdio")
