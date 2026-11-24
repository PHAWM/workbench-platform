import asyncio
import json
import logging
from typing import Any, Dict, Optional

import httpx
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 60.0


class MCPClientManager:
    """Manages MCP client connections to model service servers via SSE.

    Usage::

        client = MCPClientManager()
        result = await client.call_tool(
            server_url="http://sam-attachment-monitor:8002",
            tool_name="predict_attachment",
            arguments={"s3_key": "audits/audit_1/input/file.wav", "model_type": "all"},
        )
    """

    async def call_tool(self, server_url: str, tool_name: str,
                        arguments: Dict[str, Any],
                        timeout: float = _DEFAULT_TIMEOUT) -> Dict[str, Any]:
        sse_url = f"{server_url}/sse"
        try:
            async with asyncio.timeout(timeout):
                async with sse_client(sse_url) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        result = await session.call_tool(tool_name, arguments)
                        return self._parse_result(result)
        except asyncio.TimeoutError:
            logger.error("MCP call_tool timed out after %ss: %s/%s", timeout, server_url, tool_name)
            return {"success": False, "error": f"MCP server timed out after {timeout}s"}
        except (httpx.ReadError, httpx.ConnectError, httpx.RemoteProtocolError) as exc:
            logger.error("MCP connection error calling %s/%s: %s", server_url, tool_name, exc)
            return {"success": False, "error": f"MCP server connection lost: {exc}"}
        except Exception as exc:
            logger.exception("Unexpected error calling MCP tool %s/%s", server_url, tool_name)
            return {"success": False, "error": str(exc)}

    async def list_tools(self, server_url: str, timeout: float = _DEFAULT_TIMEOUT) -> list:
        """List available tools on a remote MCP server."""
        sse_url = f"{server_url}/sse"
        try:
            async with asyncio.timeout(timeout):
                async with sse_client(sse_url) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        tools = await session.list_tools()
                        return tools.tools
        except asyncio.TimeoutError:
            logger.error("MCP list_tools timed out after %ss: %s", timeout, server_url)
            return []
        except (httpx.ReadError, httpx.ConnectError, httpx.RemoteProtocolError) as exc:
            logger.error("MCP connection error listing tools from %s: %s", server_url, exc)
            return []
        except Exception as exc:
            logger.exception("Unexpected error listing MCP tools from %s", server_url)
            return []

    @staticmethod
    def _parse_result(result) -> Dict[str, Any]:
        """Parse MCP CallToolResult into a plain dict."""
        if not result.content:
            return {"success": False, "error": "Empty response from MCP tool"}

        # MCP tools return TextContent with JSON-encoded text
        text = result.content[0].text
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return {"success": True, "output": text}
