import os
import subprocess
import sys

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.utils.function_calling import convert_to_openai_tool


def test_log_severity_and_tenant_boundary():
    from support_agent.engine import execute
    from support_agent.domain import Session

    events = execute("read_events", {"service": "mailer", "minimum": "warning"}, Session("harbor"))
    assert "upstream response 429" in events and "queue depth 1800" in events
    assert "worker started" not in events
    isolated = execute("read_events", {"service": "mailer"}, Session("ridge"))
    assert "unknown service" in isolated and "upstream" not in isolated


def test_tools_search_and_read_only_fixtures():
    from support_agent.engine import execute
    from support_agent.domain import Session

    scope = Session("harbor")
    assert "delivery-guide" in execute("find_runbooks", {"query": "RATE LIMIT"}, scope)
    assert "MESSAGE_BATCH_SIZE = 200" in execute("inspect_config", {"path": "mailer/settings.py"}, scope)
    assert "OPS-42" in execute("lookup_incidents", {"query": "mailer"}, scope)
    assert "No matches" in execute("find_runbooks", {"query": "does-not-exist"}, scope)


def test_missing_resource_and_bad_level_are_observations():
    from support_agent.engine import execute
    from support_agent.domain import Session

    scope = Session("harbor")
    assert "mailer/settings.py" in execute("inspect_config", {"path": "mailer/setting.py"}, scope)
    assert "invalid severity" in execute("read_events", {"service": "mailer", "minimum": "trace"}, scope)


def test_tenant_is_not_a_model_argument():
    from support_agent.tools import READERS

    for reader in READERS:
        fields = convert_to_openai_tool(reader)["function"]["parameters"]["properties"]
        assert "runtime" not in fields and "tenant" not in fields


def test_raw_loop_delivers_matching_observations():
    from support_agent.demo import investigation_model
    from support_agent.engine import investigate
    from support_agent.domain import Session

    history = investigate(investigation_model(), "Why are messages delayed?", Session("harbor"))
    calls = [call for m in history if isinstance(m, AIMessage) for call in m.tool_calls]
    results = [m for m in history if isinstance(m, ToolMessage)]
    assert [call["id"] for call in calls] == [m.tool_call_id for m in results]
    assert {m.name for m in results} == {"read_events", "find_runbooks", "lookup_incidents"}
    assert "rate limiting" in history[-1].text.lower()


def test_step_limit_stops_without_another_model_request():
    from support_agent.demo import ReplayModel
    from support_agent.engine import investigate
    from support_agent.domain import Session

    repeat = AIMessage(content="", tool_calls=[{"id": "limited", "name": "read_events", "args": {"service": "mailer"}}])
    model = ReplayModel(replies=[repeat, repeat, AIMessage(content="should not execute")])
    history = investigate(model, "Investigate", Session("harbor"), turns=2)
    assert model.position == 2
    assert "turn limit" in history[-1].text.lower()
    assert len([m for m in history if isinstance(m, ToolMessage)]) == 2


def test_unsupported_answer_demo_reveals_weak_stop_rule():
    from support_agent.demo import unsupported_model
    from support_agent.engine import investigate
    from support_agent.domain import Session

    history = investigate(unsupported_model(), "What is the batch size?", Session("harbor"))
    result = next(m for m in history if isinstance(m, ToolMessage))
    assert "not found" in result.text
    assert "20" in history[-1].text


def test_compiled_agent_uses_tools_then_validates_report():
    from support_agent.demo import investigation_model
    from support_agent.engine import build
    from support_agent.domain import Report, Session

    state = build(investigation_model(structured=True)).invoke({"messages": [("user", "Investigate mailer delays")]}, context=Session("harbor"))
    report = state["structured_response"]
    assert isinstance(report, Report)
    assert report.confidence == "medium"
    assert "429" in report.findings[0].evidence
    tools = {m.name for m in state["messages"] if isinstance(m, ToolMessage)}
    assert {"read_events", "find_runbooks", "lookup_incidents"} <= tools


def test_compiled_agent_streams_progress_and_exposes_graph():
    from support_agent.demo import investigation_model
    from support_agent.engine import build
    from support_agent.domain import Session

    agent = build(investigation_model(structured=True))
    updates = list(agent.stream({"messages": [("user", "Investigate") ]}, context=Session("harbor"), stream_mode="updates"))
    assert any("tools" in update for update in updates)
    assert any("structured_response" in value for update in updates for value in update.values() if value)
    assert "model" in agent.get_graph().draw_mermaid()


def test_environment_settings_and_trace_metadata(monkeypatch):
    from support_agent.domain import ModelSettings, Session
    from support_agent.engine import trace_options

    monkeypatch.setenv("SUPPORT_MODEL", "openai:example")
    monkeypatch.setenv("SUPPORT_TEMPERATURE", "none")
    monkeypatch.setenv("SUPPORT_REPLY_TOKENS", "512")
    settings = ModelSettings.from_environment()
    assert settings.model == "openai:example" and settings.temperature is None
    assert settings.reply_tokens == 512
    options = trace_options(Session("harbor", user="operator"))
    assert "tenant:harbor" in options["tags"]
    assert options["metadata"]["user"] == "operator"


def test_cli_offline_stream_prints_structured_report():
    completed = subprocess.run([sys.executable, "-m", "support_agent", "--offline"],
                               text=True, capture_output=True, env={**os.environ, "LANGSMITH_TRACING": "false"})
    assert completed.returncode == 0, completed.stderr
    assert "read_events" in completed.stdout and '"confidence": "medium"' in completed.stdout


def test_cli_known_failure_is_labeled():
    completed = subprocess.run([sys.executable, "-m", "support_agent", "--offline", "--raw", "--unsupported"],
                               text=True, capture_output=True, env={**os.environ, "LANGSMITH_TRACING": "false"})
    assert completed.returncode == 0, completed.stderr
    assert "NOT VERIFIED" in completed.stdout and "not found" in completed.stdout
    assert "batch size is 20" in completed.stdout
