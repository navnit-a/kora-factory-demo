import os

from fastmcp import FastMCP

LOOPBACK = "127.0.0.1"
PATH = "/mcp"


def bind_host() -> str:
    return os.environ.get("BIND_HOST", LOOPBACK)


def serve(mcp: FastMCP) -> None:
    port = int(os.environ.get("PORT", "8000"))
    mcp.run(transport="http", host=bind_host(), port=port, path=PATH, show_banner=False)
