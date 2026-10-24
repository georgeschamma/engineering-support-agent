import os

from langchain.mcp import MCPAdapter
from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from support_agent.engine import build, trace_options

server = MCPServer("delivery-operations-demo")


@server.tool(annotations=ToolAnnotations(readOnlyHint=True))
def deployment_flag(flag: str) -> str:
    """Read a fictional rollout flag by name."""
    return {"grouped_delivery": "enabled in sandbox"}.get(flag, "Flag not found.")


@server.tool(annotations=ToolAnnotations(readOnlyHint=True))
def dependency_status(dependency: str) -> str:
    """Read the fictional health of an upstream dependency."""
    return {"outbound-relay": "rate limited; HTTP 429 responses observed"}.get(dependency, "Dependency not found.")


async def investigate_remote(model, url, question, session, observe=None):
    async with MCPAdapter(url) as connection:
        agent = build(model, await connection.list_tools())
        result = {}
        async for update in agent.astream({"messages": [("user", question)]}, context=session,
                                         config=trace_options(session), stream_mode="updates"):
            for node, values in update.items():
                if values:
                    result.update(values)
                    if observe:
                        observe(node, values)
        return result


if __name__ == "__main__":
    server.run(transport="streamable-http", host="127.0.0.1",
               port=int(os.environ.get("SUPPORT_MCP_PORT", "8876")))
