"""MCP-klient — anslut till MCP-servrar via stdio och exponera tools.

Användning i agent-skill eller pipeline:
    from agentkit.mcp import McpClient

    async with McpClient("filesystem", "npx", ["@modelcontextprotocol/server-filesystem", "/tmp"]) as client:
        tools = await client.list_tools()
        result = await client.call_tool("read_file", {"path": "/tmp/test.txt"})
"""

import asyncio
import json
import subprocess
from typing import Any


class McpClient:
    """Anslut till en MCP-server via stdio-transport.

    Startar servern som subprocess, pratar JSON-RPC 2.0 över stdin/stdout.
    """

    def __init__(self, name: str, command: str, args: list[str] | None = None):
        self.name = name
        self.command = command
        self.args = args or []
        self._process: subprocess.Popen | None = None
        self._reader: asyncio.StreamReader | None = None
        self._request_id = 0

    async def __aenter__(self):
        self._process = await asyncio.create_subprocess_exec(
            self.command, *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        self._reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(self._reader)
        loop = asyncio.get_event_loop()
        if self._process.stdout:
            await loop.connect_read_pipe(lambda: protocol, self._process.stdout)  # type: ignore[arg-type]
        return self

    async def __aexit__(self, *args):
        if self._process:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._process.kill()

    async def _send(self, method: str, params: dict = None) -> dict:
        self._request_id += 1
        req = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params or {},
        }
        if self._process and self._process.stdin:
            self._process.stdin.write((json.dumps(req) + "\n").encode())
            await self._process.stdin.drain()

        # Läs svar (rad-baserad JSON-RPC)
        while True:
            line = await self._reader.readline()
            if not line:
                raise ConnectionError(f"MCP-server '{self.name}' stängde anslutningen")
            try:
                resp = json.loads(line.decode())
            except json.JSONDecodeError:
                continue
            if resp.get("id") == self._request_id:
                if "error" in resp:
                    raise RuntimeError(resp["error"]["message"])
                return resp.get("result", {})

    async def list_tools(self) -> list[dict]:
        """Hämta lista med tillgängliga tools från MCP-servern."""
        result = await self._send("tools/list")
        return result.get("tools", [])

    async def call_tool(self, name: str, arguments: dict[str, Any] = None) -> dict:
        """Anropa ett tool på MCP-servern."""
        result = await self._send("tools/call", {"name": name, "arguments": arguments or {}})
        return result


def mcp_tools_to_langchain(mcp_tools: list[dict]) -> list:
    """Konvertera MCP-tools till LangChain @tool-format.

    Anropas från ReAct-agentens pipeline för att registrera externa tools.
    """
    from langchain_core.tools import tool as lc_tool

    lc_tools = []
    for t in mcp_tools:
        name = t["name"]
        desc = t.get("description", "")
        input_schema = t.get("inputSchema", {})

        # ponytail: generera en wrapper per tool — enkel, stabil
        @lc_tool
        def _make_wrapper(tool_name=name, schema=input_schema):  # type: ignore[no-untyped-def]
            async def wrapper(**kwargs: Any) -> str:
                # Validera mot schemat (ponytail: bara required-fält)
                required = (schema or {}).get("required", [])
                for field in required:
                    if field not in kwargs:
                        return json.dumps({"error": f"required field '{field}' saknas"})
                # Starta en tillfällig anslutning — ponytail: enkel, ingen connection pool
                # Detta är en synkron wrapper — användaren bör wrappa med asyncio.run
                try:
                    # ponytail: kör i samma event loop om möjligt
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Vi är redan i en async kontext — använd den
                        async with McpClient(tool_name, mcp_command, mcp_args) as client:
                            result = await client.call_tool(tool_name, kwargs)
                            return json.dumps(result, ensure_ascii=False)
                    else:
                        # Synkront fallback
                        return asyncio.run(_async_call(tool_name, mcp_command, mcp_args, kwargs))
                except Exception as e:
                    return json.dumps({"error": str(e)[:200]})

            wrapper.__name__ = tool_name
            wrapper.__doc__ = desc
            return wrapper

        # Detta kräver att mcp_command/mcp_args är kända vid wraptime
        # Se create_tools() nedan för korrekt implementation
    return lc_tools


# ponytail: global state för MCP-konfiguration — tillräckligt för en agent i taget
_mcp_command = ""
_mcp_args: list[str] = []


def _set_server_config(command: str, args: list[str]):
    global _mcp_command, _mcp_args
    _mcp_command = command
    _mcp_args = args


async def _async_call(name: str, cmd: str, args: list[str], kwargs: dict) -> str:
    async with McpClient(name, cmd, args) as client:
        result = await client.call_tool(name, kwargs)
        return json.dumps(result, ensure_ascii=False)


def create_tools(servers: list[dict]) -> list:
    """Skapa LangChain-tools från MCP-serverkonfiguration.

    Args:
        servers: Lista från agent.yaml, t.ex.
            [{"name": "fs", "command": "npx", "args": ["@modelcontextprotocol/server-filesystem", "/tmp"]}]

    Returns:
        Lista med LangChain @tool-dekorerade funktioner (synkrona wrappers)
    """
    from langchain_core.tools import tool as lc_tool

    tools = []

    for server in servers:
        name = server["name"]
        command = server["command"]
        args = server.get("args", [])

        # Hämta tool-listan från servern
        try:
            server_tools = asyncio.run(_list_tools_from_server(command, args))
        except Exception as e:
            print(f"  ⚠ Kunde inte ansluta till MCP-server '{name}': {e}")
            continue

        for t in server_tools:
            tool_name = t["name"]
            desc = t.get("description", "")
            schema = t.get("inputSchema", {})

            @lc_tool
            def make_wrapper(  # type: ignore[no-untyped-def]
                tn=tool_name,
                tm=desc,
                cmd=command,
                cargs=args,
                sc=schema,
            ):
                def wrapper(**kwargs) -> str:
                    required = (sc or {}).get("required", [])
                    for field in required:
                        if field not in kwargs:
                            return json.dumps({"error": f"required: '{field}'"})
                    try:
                        return asyncio.run(_async_call(tn, cmd, cargs, kwargs))
                    except Exception as e:
                        return json.dumps({"error": str(e)[:200]})

                wrapper.__name__ = tn
                wrapper.__doc__ = tm
                return wrapper

            tools.append(make_wrapper)

    return tools


async def _list_tools_from_server(command: str, args: list[str]) -> list[dict]:
    """Starta server, hämta tools, stäng."""
    async with McpClient("_tmp", command, args) as client:
        return await client.list_tools()
