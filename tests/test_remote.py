import asyncio
import os
import socket
import subprocess
import sys
import time


def test_local_mcp_discovery_calls_and_agent_integration():
    from langchain.mcp import MCPAdapter
    from support_agent.remote import investigate_remote
    from support_agent.demo import remote_model
    from support_agent.domain import Session

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    environment = {**os.environ, "SUPPORT_MCP_PORT": str(port), "LANGSMITH_TRACING": "false"}
    process = subprocess.Popen([sys.executable, "-m", "support_agent.remote"], env=environment,
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise AssertionError(process.stderr.read())
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.05)
        else:
            raise AssertionError("Local MCP server did not start")

        async def check():
            url = f"http://127.0.0.1:{port}/mcp"
            async with MCPAdapter(url) as adapter:
                tools = {reader.name: reader for reader in await adapter.list_tools()}
                assert set(tools) == {"deployment_flag", "dependency_status"}
                flag = await tools["deployment_flag"].ainvoke({"flag": "grouped_delivery"})
                health = await tools["dependency_status"].ainvoke({"dependency": "outbound-relay"})
                assert any(block.get("text") == "enabled in sandbox" for block in flag)
                assert any(block.get("text") == "rate limited; HTTP 429 responses observed" for block in health)
            state = await investigate_remote(remote_model(), url, "Inspect delivery", Session("harbor"))
            assert "rate limited" in state["structured_response"].findings[0].evidence

        asyncio.run(check())
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        process.stderr.close()
