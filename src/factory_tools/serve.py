import os

from fastmcp import FastMCP

HOST = "0.0.0.0"
PATH = "/mcp"


def serve(mcp: FastMCP) -> None:
    port = int(os.environ.get("PORT", "8000"))
    mcp.run(transport="http", host=HOST, port=port, path=PATH, show_banner=False)
