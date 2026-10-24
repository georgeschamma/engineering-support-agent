from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class ReplayModel(BaseChatModel):
    """Replay model messages while real tools and graph nodes execute."""

    replies: list[AIMessage]
    position: int = 0

    @property
    def _llm_type(self):
        return "local-transcript-replay"

    def bind_tools(self, tools, **kwargs):
        return self.bind(tools=tools, **kwargs)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        reply = self.replies[self.position]
        self.position += 1
        return ChatResult(generations=[ChatGeneration(message=reply)])


def request(name, arguments, identifier):
    return AIMessage(content="", tool_calls=[{"name": name, "args": arguments, "id": identifier}])


def investigation_model(structured=False):
    replies = [
        request("read_events", {"service": "mailer", "minimum": "warning"}, "events-1"),
        request("find_runbooks", {"query": "rate limits"}, "docs-2"),
        request("lookup_incidents", {"query": "mailer"}, "history-3"),
    ]
    summary = "Message delivery is delayed while the upstream relay applies rate limiting."
    report = {
        "summary": summary,
        "findings": [
            {"claim": "The relay is rejecting requests.", "evidence": "2026-10-13T08:02:00Z upstream response 429; retry delayed 30s"},
            {"claim": "Pending messages are accumulating.", "evidence": "2026-10-13T08:03:00Z queue depth 1800; oldest message age 240s"},
        ],
        "confidence": "medium",
        "next_step": "Inspect the upstream quota and current batch size before proposing a change.",
    }
    replies.append(request("Report", report, "report-4") if structured else AIMessage(content=summary))
    return ReplayModel(replies=replies)


def unsupported_model():
    return ReplayModel(replies=[
        request("inspect_config", {"path": "mailer/setting.py"}, "missing-1"),
        AIMessage(content="The message batch size is 20."),
    ])


def remote_model():
    return ReplayModel(replies=[
        AIMessage(content="", tool_calls=[
            {"name": "deployment_flag", "args": {"flag": "grouped_delivery"}, "id": "flag-1"},
            {"name": "dependency_status", "args": {"dependency": "outbound-relay"}, "id": "health-2"},
        ]),
        request("Report", {
            "summary": "Grouped delivery is enabled; the outbound relay is rate limited.",
            "findings": [{"claim": "The relay is constrained.", "evidence": "rate limited; HTTP 429 responses observed"}],
            "confidence": "medium", "next_step": "Inspect the relay quota.",
        }, "remote-report-3"),
    ])
