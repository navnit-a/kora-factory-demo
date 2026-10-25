import asyncio
import json
import ssl
import sys
from pathlib import Path

import httpx
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from factory_demo.cli import run_cli  # noqa: E402
from factory_demo.kora_api import (  # noqa: E402
    DEFAULT_API_URL,
    DEFAULT_CREDENTIALS,
    default_ca_file,
    read_credentials,
)
from factory_demo.tools_check import SERVERS, missing_tools, reachable_line  # noqa: E402

TIMEOUT_S = 60.0


def client_factory(context: ssl.SSLContext):
    def factory(**kwargs) -> httpx.AsyncClient:
        rest = {k: v for k, v in kwargs.items() if k not in ("verify", "timeout")}
        return httpx.AsyncClient(verify=context, timeout=httpx.Timeout(TIMEOUT_S), **rest)

    return factory


async def list_tools(server: str, token: str, context: ssl.SSLContext) -> list[str]:
    transport = StreamableHttpTransport(
        f"{DEFAULT_API_URL}/v1/mcp/{server}",
        headers={"Authorization": f"Bearer {token}"},
        httpx_client_factory=client_factory(context),
    )
    async with Client(transport, timeout=TIMEOUT_S) as client:
        return [tool.name for tool in await client.list_tools()]


def main() -> int:
    token = read_credentials(DEFAULT_CREDENTIALS)["access_token"]
    context = ssl.create_default_context(cafile=default_ca_file())
    listed = {server: asyncio.run(list_tools(server, token, context)) for server in SERVERS}
    for server, tools in listed.items():
        print(f"ok   {server} lists {len(tools)} tool(s) through the gateway")
    missing = missing_tools(listed)
    for tool in missing:
        print(f"FAIL {tool} not listed by the gateway")
    print(json.dumps({"missing": missing}) if missing else reachable_line())
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(run_cli(main))
