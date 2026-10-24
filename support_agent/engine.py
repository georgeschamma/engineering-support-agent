from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain.chat_models import init_chat_model
from langchain.tools import ToolRuntime
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from support_agent.domain import ModelSettings, Report, Session
from support_agent.tools import READERS

INSTRUCTIONS = (
    "Investigate engineering incidents with the available read-only tools. "
    "Separate observed facts from possible causes. Attribute findings to the observations "
    "you received. A missing resource is not evidence of its contents. "
    "Recommend a next diagnostic step; do not claim to have changed any service."
)


def live_model():
    settings = ModelSettings.from_environment()
    return init_chat_model(settings.model, temperature=settings.temperature,
                           max_tokens=settings.reply_tokens, timeout=settings.request_timeout)


def execute(name: str, arguments: dict, session: Session, call_id: str = "direct") -> str:
    reader = next(item for item in READERS if item.name == name)
    runtime = ToolRuntime(state={}, context=session, config={}, store=None,
                          stream_writer=lambda _: None, tool_call_id=call_id)
    return str(reader.invoke({**arguments, "runtime": runtime}))


def investigate(model, question: str, session: Session, turns: int = 10, observe=None):
    conversation = [SystemMessage(INSTRUCTIONS), HumanMessage(question)]
    connected = model.bind_tools(READERS)
    for _ in range(turns):
        reply = connected.invoke(conversation)
        conversation.append(reply)
        if observe:
            observe(reply)
        if not reply.tool_calls:
            return conversation
        for request in reply.tool_calls:
            result = ToolMessage(
                content=execute(request["name"], request["args"], session, request["id"]),
                tool_call_id=request["id"], name=request["name"],
            )
            conversation.append(result)
            if observe:
                observe(result)
    stopped = AIMessage(content="Investigation stopped at the model turn limit.")
    conversation.append(stopped)
    if observe:
        observe(stopped)
    return conversation


def build(model, additional_tools=()):
    return create_agent(model=model, tools=[*READERS, *additional_tools],
                        context_schema=Session, system_prompt=INSTRUCTIONS,
                        response_format=ToolStrategy(Report))


def trace_options(session: Session):
    return {"run_name": "engineering-support-investigation",
            "tags": [f"tenant:{session.tenant}", f"role:{session.role}", f"environment:{session.environment}"],
            "metadata": {"user": session.user}}
